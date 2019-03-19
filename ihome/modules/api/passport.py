# 实现图片验证码和短信验证码的逻辑
import re, random
from flask import request, abort, current_app, jsonify, make_response, json, session

from ihome import sr, db
from ihome.libs.captcha.pic_captcha import captcha
from ihome.libs.yuntongxun.sms import CCP
from ihome.models import User
from ihome.modules.api import api_blu
from ihome.utils import constants
from ihome.utils.response_code import RET


# 获取图片验证码
@api_blu.route("/imagecode")
def get_image_code():
    """
    1. 获取传入的验证码编号，并编号是否有值
    2. 生成图片验证码
    3. 保存编号和其对应的图片验证码内容到redis
    4. 返回验证码图片
    :return:
    """
    cur = request.args.get("cur")
    print(cur)

    if not cur:
        return abort(404)

    # 2. 生成图片验证码
    image_name, real_image_code, image_data = captcha.generate_captcha()

    # 3. 保存编号和其对应的图片验证码内容到redis
    try:
        sr.setex("Image_Code_%s" % cur, constants.IMAGE_CODE_REDIS_EXPIRES, real_image_code)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='保存数据错误')

    # 4. 返回验证码图片
    response = make_response(image_data)
    response.headers["Content-Type"] = "image/png"
    return response


# 获取短信验证码
@api_blu.route('/smscode', methods=["POST"])
def send_sms():
    """
    1. 接收参数并判断是否有值
    2. 校验手机号是正确
    3. 通过传入的图片编码去redis中查询真实的图片验证码内容
    4. 进行验证码内容的比对
    5. 生成发送短信的内容并发送短信
    6. redis中保存短信验证码内容
    7. 返回发送成功的响应
    :return:
    """
    # 1.
    # 接收参数并判断是否有值
    parm = request.json
    # 1.1 获取参数 手机mobile 用户输入的图形验证码内容image_code 真实的图片验证码编号
    mobile = parm.get('mobile')
    image_code = parm.get('image_code')
    image_code_id = parm.get('image_code_id')
    if not all([mobile, image_code, image_code_id]):
        return jsonify(errno=RET.PARAMERR, errmsg='参数不足')
    print(image_code_id)

    # 2.
    # 校验手机号是正确
    if not re.match(r'^1[3578][0-9]{9}$', mobile):
        return jsonify(errno=RET.DATAERR, errmsg='手机号码格式错误')

    # 3.
    # 通过传入的图片编码去redis中查询真实的图片验证码内容
    # todo 查看参数是否与保存验证码到redis时的真实值是否一致
    try:
        really = sr.get('Image_Code_%s' % image_code_id)
    except Exception as e:
        return jsonify(errno=RET.DBERR, errmag='查询图形验证码异常')
    print(really)

    if really:
        sr.delete('Image_Code_%s' % image_code_id)
    else:
        return jsonify(errno=RET.NODATA, errmsg='数据库么有该数据')

    # 4.
    # 进行验证码内容的比对

    if image_code.lower() != really.lower():
        return jsonify(errno=RET.DATAERR, errmsg='用户填写验证码错误')

    # 5.
    # 生成发送短信的内容并发送短信
    # 判断手机号码是否已经注册
    try:
        user = User.query.filter(User.mobile == mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='查询用户数据错误')
    if user:
        return jsonify(errno=RET.DATAEXIST, errmsg='手机号码已经注册')
    # todo 可以添加一个找回密码功能

    # 生成6位数字验证码

    really_sms_code = random.randint(0, 999999)
    really_sms_code = '%06d' % really_sms_code

    # 调用CPP对象的send_template_sms发送短信验证码
    # 参数1：手机号，参数2：发送的短信内容以及过期时间，参数3 ：短信模板id
    try:
        result = CCP().send_template_sms(mobile, [really_sms_code, 5], 1)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg='云通讯异常')

    # 发送验证码失败
    if result == -1:
        return jsonify(errno=RET.THIRDERR, errmsg='云通讯发送异常')
    # 6.
    # redis中保存短信验证码内容
    # todo 注意之后注册比较时查看保存的key与取值的key是否一致
    sr.setex('SMS_CODE_%s' % mobile, constants.SMS_CODE_REDIS_EXPIRES, really_sms_code)
    # 7.
    # 返回发送成功的响应
    return jsonify(errno=RET.OK, errmsg='发送短信验证码成功')


# 用户注册
@api_blu.route("/user", methods=["POST"])
def register():
    """
    1. 获取参数和判断是否有值
    2. 从redis中获取指定手机号对应的短信验证码的
    3. 校验验证码
    4. 初始化 user 模型，并设置数据并添加到数据库
    5. 保存当前用户的状态
    6. 返回注册的结果
    :return:
    """
    # 1. 获取参数和判断是否有值（mobile：手机号  phonecode：短信验证码 password：密码）
    prama_dict = request.json
    mobile = prama_dict.get("mobile")
    sms_code = prama_dict.get("phonecode")
    password = prama_dict.get("password")

    # 非空判断
    if not all([mobile, password, sms_code]):
        current_app.logger.error("参数不足")
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")
    # 手机号码判断
    if not re.match(r"^1[3578][0-9]{9}", mobile):
        return jsonify(errno=RET.PARAMERR, errmsg="手机号码格式错误")

    # 2. 从redis中获取指定手机号对应的短信验证码的(sr: redis数据库对象)
    try:
        real_sms_code = sr.get("SMS_CODE_%s" % mobile)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询redis中短信验证码异常")

    # 短信验证码有值：从Redis数据库删除【避免同一个验证码多次验证码】
    if real_sms_code:
        sr.delete("SMS_CODE_%s" % mobile)
        #  短信验证码没有值：短信验证码过期了
    else:
        return jsonify(errno=RET.NODATA, errmsg="短信验证码过期")

    # 3. 校验验证码
    if sms_code != real_sms_code:
        return jsonify(errno=RET.DATAERR, errmsg="短息验证码填写错误")

    # 相等：使用User类创建实例对象，给其各个属性赋值
    user = User()
    # 昵称
    user.name = mobile
    # 手机号码
    user.mobile = mobile
    # 动态添加password
    user.password = password

    # 4. 初始化 user 模型，并设置数据并添加到数据库
    try:
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        # 如果提交失败，数据回滚
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存用户对象异常")
    # 5. 保存当前用户的状态
    session["user_id"] = user.id
    session["name"] = user.name
    session["mobile"] = user.mobile
    # 6. 返回注册的结果
    return jsonify(errno=RET.OK, errmsg="注册成功")


# 用户登录
@api_blu.route("/session", methods=["POST"])
def login():
    """
    1. 获取参数和判断是否有值
    2. 从数据库查询出指定的用户
    3. 校验密码
    4. 保存用户登录状态
    5. 返回结果
    """
    # 1. 获取参数和判断是否有值
    mobile = request.json.get("mobile")
    password = request.json.get("password")
    if not all([mobile, password]):
        current_app.logger.error("参数不足")
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")
    if not re.match(r"1[34578]\d{9}",mobile):
        return jsonify(errno=RET.PARAMERR, errmsg="手机格式错误")

    # 2. 从数据库查询出指定的用户
    try:
        user = User.query.filter(User.mobile == mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库查询错误")

    # 3. 校验密码
    if not user:
        return jsonify(errno=RET.USERERR, errmsg="用户不存在或未激活")
    if not user.check_passowrd(password):
        return jsonify(errno=RET.LOGINERR, errmsg="用户登录失败")

    # 4. 保存用户登录状态
    session["user_id"] = user.id
    session["name"] = user.name
    session["mobile"] = user.mobile

    # 5. 返回结果
    return jsonify(errno=RET.OK, errmsg="成功")


# 获取登录状态
@api_blu.route('/session')
def check_login():
    """
    检测用户是否登录，如果登录，则返回用户的名和用户id
    :return:
    """
    name = session.get("name")
    user_id = session.get("user_id")

    if not all([name, user_id]):
        return jsonify(errno=RET.SESSIONERR, errmsg="未登录")

    data = {
        "name": name,
        "user_id": user_id
    }
    return jsonify(errno=RET.OK, errmsg="OK", data=data)


# 退出登录
@api_blu.route("/session", methods=["DELETE"])
def logout():
    """
    1. 清除session中的对应登录之后保存的信息
    :return:
    """

    session.pop("user_id", None)
    session.pop("mobile", None)
    session.pop("name", None)

    return jsonify(errno=RET.OK, errmsg="退出成功")
