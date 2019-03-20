from flask import request, current_app, jsonify, session, g

from ihome import db
from ihome.models import User
from ihome.modules.api import api_blu
from ihome.utils import constants
from ihome.utils.common import login_required
from ihome.utils.constants import QINIU_DOMIN_PREFIX
from ihome.utils.image_storage import storage_image
from ihome.utils.response_code import RET


# 获取用户信息
@api_blu.route('/user')
@login_required
def get_user_info():
    """
    获取用户信息
    1. 获取到当前登录的用户模型
    2. 返回模型中指定内容
    :return:
    """
    # 1.获取到当前登录的用户模型
    user_id = g.user_id

    try:
        user = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="")

    if not user:
        return jsonify(errno=RET.NODATA, errmsg="用户不存在")

    # 2.返回模型中指定内容
    return jsonify(errno=RET.OK, errmsg="OK", data=user.to_dict())


# 修改用户名
@api_blu.route('/user/name', methods=["POST"])
@login_required
def set_user_name():
    """
    0. 判断用户是否登录
    1. 获取到传入参数
    2. 将用户名信息更新到当前用户的模型中
    3. 返回结果
    :return:
    """
    user_id = g.user_id
    # 判断用户是否已经登录
    if not user_id:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户尚未登录")
    # 根据用户id获取用户对象
    try:
        user = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库查询错误")
    # 判断user是否存在
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户不存在")
    # 获取参数
    new_name = request.json.get("name")
    if not new_name:
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")
    # 查询新用户名是否已经被占用
    other_user = None
    try:
        other_user = User.query.filter(User.name == new_name).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库查询错误")
    if other_user:
        return jsonify(errno=RET.DATAEXIST, errmsg="用户名已被占用")
    # 将新用户名保存到数据库
    user.name = new_name
    session["name"] = new_name
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="数据库保存错误")
    return jsonify(errno=RET.OK, errmsg="修改成功")


# 上传个人头像
@api_blu.route('/user/avatar', methods=['POST'])
@login_required
def set_user_avatar():
    """
    0. 判断用户是否登录
    1. 获取到上传的文件
    2. 再将文件上传到七牛云
    3. 将头像信息更新到当前用户的模型中
    4. 返回上传的结果<avatar_url>
    :return:
    """
    # 0. 判断用户是否登录
    user_id = g.user_id
    user = User.query.get(user_id)
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    # 1. 获取到上传的文件
    avatar = request.files.get("avatar")
    if not avatar:
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")

    # 2. 再将文件上传到七牛云
    try:
        avatar_image = storage_image(avatar.read())
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="第三方系统错误")
    if not avatar_image:
        return jsonify(errno=RET.NODATA, errmsg="无数据")

    # 3. 将头像信息更新到当前用户的模型中
    user.avatar_url = avatar_image
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="数据库提交错误")

    # 4. 返回上传的结果<avatar_url>
    avatar_url = constants.QINIU_DOMIN_PREFIX + avatar_image
    return jsonify(errno=RET.OK, errmsg="成功", avatar_url=avatar_url)


# 获取用户实名信息
@api_blu.route('/user/auth')
@login_required
def get_user_auth():
    """
    1. 取到当前登录用户id
    2. 通过id查找到当前用户
    3. 获取当前用户的认证信息
    4. 返回信息
    :return:
    """
    pass


# 设置用户实名信息
@api_blu.route('/user/auth', methods=["POST"])
@login_required
def set_user_auth():
    """
    1. 取到当前登录用户id
    2. 取到传过来的认证的信息
    3. 通过id查找到当前用户
    4. 更新用户的认证信息
    5. 保存到数据库
    6. 返回结果
    :return:
    """
    pass
