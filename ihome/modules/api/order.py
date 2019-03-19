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
        if (start_date <= house_order.begin_date < end_date) or (start_date < house_order.end_date < end_date) or (house_order.begin_date <= start_date and house_order.end_date > end_date):
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
    pass


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
    pass


# 评论订单
@api_blu.route('/orders/comment', methods=["PUT"])
@login_required
def order_comment():
    """
    订单评价
    1. 获取参数
    2. 校验参数
    3. 修改模型
    :return:
    """
    pass
