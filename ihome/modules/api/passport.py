# 实现图片验证码和短信验证码的逻辑
import re, random
from flask import request, abort, current_app, jsonify, make_response, json, session

from ihome import sr, db
from ihome.libs.captcha.pic_captcha import captcha
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
    pass



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
    pass


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
    if not re.match(r"1[3578][0-9]{9}", mobile):
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
    user.nick_name = mobile
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
    session["nick_name"] = user.nick_name
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
    :return:
    """
    pass


# 获取登录状态
@api_blu.route('/session')
def check_login():
    """
    检测用户是否登录，如果登录，则返回用户的名和用户id
    :return:
    """
    pass


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
