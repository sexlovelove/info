import datetime

from ihome import db, sr
from ihome.models import House, Order, User
from ihome.utils.common import login_required
from ihome.utils.response_code import RET
from . import api_blu
from flask import request, g, jsonify, current_app


# 预订房间
@api_blu.route('/orders', methods=['POST'])
@login_required
def add_order():
    """
    下单
    1. 获取参数
    2. 校验参数
    3. 查询指定房屋是否存在
    4. 判断当前房屋的房主是否是登录用户
    5. 查询当前预订时间是否存在冲突
    6. 生成订单模型，进行下单
    7. 返回下单结果
    :return:
    """
    # 1. 获取参数
    user_id = g.user_id
    house_id = request.json.get("house_id")
    start_date = request.json.get("start_date")
    end_date = request.json.get("end_date")

    # 2. 校验参数
    if not all([house_id, start_date, end_date]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")
    if not user_id:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")
    # 字符串格式的时间转换为日期格式的时间
    try:
        start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="格式错误")
    if start_date <= end_date:
        return jsonify(errno=RET.PARAMERR, errmsg="格式错误")
    # 预定天数
    days = end_date - start_date

    # 3. 查询指定房屋是否存在
    try:
        house = House.query.get(house_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库查询错误")
    if not house:
        return jsonify(errno=RET.NODATA, errmsg="无房屋可预定")

    # 4. 判断当前房屋的房主是否是登录用户
    try:
        house_user = House.query.filter(House.user_id == user_id).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库查询错误")
    if house_user:
        return jsonify(errno=RET.PARAMERR, errmsg="房主是登录用户")

    # 5. 查询当前预订时间是否存在冲突
    # 查询当前房屋的所有订单
    house_orders = house.orders
    # i用来记录订单冲突数量
    i = 0
    # 对所有订单进行遍历,如果中途出现有时间冲突的,其实就可以退出了,如果一直没有碰到有时间冲突的,那么就要遍历到最后一个,确保所有的订单都没有时间冲突
    for house_order in house_orders:
        # 如果发生时间冲突(别人的开始时间或者结束时间在我的预定开始时间内,都是不符合的)
        if (start_date <= house_order.begin_date < end_date) or (start_date < house_order.end_date < end_date):
            i += 1
            break
    if i > 0:
        return jsonify(errno=RET.PARAMERR, errmsg="无法预定")

    # 6. 生成订单模型，进行下单
    order = Order()
    order.user_id = user_id
    order.house_id = house_id
    order.begin_date = start_date
    order.end_date = end_date
    order.days = days
    order.house_price = house.price
    order.amount = days * house.price
    order.status = "WAIT_ACCEPT"
    try:
        db.session.add(order)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存数据库异常")

    # 7. 返回下单结果
    data = order.id
    return jsonify(errno=RET.OK, errmsg="成功", data=data)


# 获取我的订单
@api_blu.route('/orders')
@login_required
def get_orders():
    """
    1. 去订单的表中查询当前登录用户下的订单
    2. 返回数据
    :return:
    """
    # 判断用户是否登录
    user_id = g.user_id
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
        return jsonify(errno=RET.NODATA, errmsg="用户不存在")
    # 判断当前是什么角色发送请求
    role = request.args.get("role")
    if not role:
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")
    if role not in (["custom", "landlord"]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
    # 房客角色发送查看订单请求
    if role == "custom":
        order_dict_list = []
        order_list = []
        order_list = user.orders
        for order in order_list if order_list else []:
            order_dict_list.append(order.to_dict())
        data = {
            "orders": order_dict_list
        }
        return jsonify(errno=RET.OK, errmsg="ok", data=data)
    # 房东角色发送请求
    else:
        # 用户发布的房子的id列表
        houses_id_list = [house.id for house in user.houses]
        # 属于该房东的订单
        landlord_order_list = Order.query.filter(Order.house_id.in_(houses_id_list)).order_by(Order.create_time).all()
        # 转化为字典列表
        landlord_order_dict_list = []
        for landlord_order in landlord_order_list if landlord_order_list else []:
            landlord_order_dict_list.append(landlord_order.to_dict())
        data = {
            "orders": landlord_order_dict_list
        }
        return jsonify(errno=RET.OK, errmsg="ok", data=data)


# 接受/拒绝订单
@api_blu.route('/orders', methods=["PUT"])
@login_required
def change_order_status():
    """
    1. 接受参数：order_id
    2. 通过order_id找到指定的订单，(条件：status="待接单")
    3. 修改订单状态
    4. 保存到数据库
    5. 返回
    :return:
    """
    # 1.接受参数：order_id
    user_id = g.user_id
    action = request.json.get("action")
    order_id = request.json.get("order_id")

    if not user_id:
        return jsonify(errno=RET.NODATA, errmsg="请登录")

    if not all([order_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
    if action not in ("accept", "reject"):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 2.通过order_id找到指定的订单
    order = None
    try:
        order = Order.query.filter(Order.id == order_id, Order.status == "WAIT_ACCEPT").first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="未查询到数据")

    # 3. 修改订单状态
    if action == "accept":
        order.status = "WAIT_PAYMENT"
    else:
        reason = request.json.get("reason")
        if not reason:
            return jsonify(errno=RET.NODATA, errmsg="原因为空")
        order.comment = reason
        order.status = "REJECTED"

    # 4.保存到数据库
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据保存失败")

    # 5.返回
    return jsonify(errno=RET.OK, errmsg="OK")


# 评论订单
@api_blu.route('/orders/comment', methods=["PUT"])
@login_required
def order_comment(order_id):
    """
    订单评价
    1. 获取参数
    2. 校验参数
    3. 修改模型
    :return:
    """
    # 1.获取参数(user_id:当前登录的用户对象 comment: 评论对象)
    param_dict = request.json
    comment = param_dict.get("comment")
    order_id = param_dict.get("order_id")
    user_id = g.user_id
    # 2.校验参数
    # 非空判断
    if not comment:
        return jsonify(errno=RET.PARAMERR, errmsg="请输入评论内容")

    # 通过订单id查询出订单模型
    # 确保用户只能评价自己的订单并且订单处于待评价状态
    try:
        order = Order.query.filter(Order.id == order_id, Order.status == "WAIT_COMMENT").first()
        house = order.house
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询订单数据错误")

    # 判断该订单是否存在
    if not all([order, house]):
        return jsonify(errno=RET.NODATA, errmsg="不存在该订单")

    # 3.修改模型
    # 将订单状态设置为完成
    order.status = "COMPLETE"
    # 保存订单的评价信息
    order.comment = comment
    # 将房屋的订单完成数量加1
    house.order_count += 1

    # 保存数据
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存数据失败")

    # 删除该房屋的redis缓存
    try:
        sr.delete("house_info_%s" % house.id)
    except Exception as e:
        current_app.logger.error(e)

    return jsonify(errno=RET.OK, errmsg="OK", data=comment)
