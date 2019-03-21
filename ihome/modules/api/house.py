import datetime

from flask import current_app, jsonify, request, g, session
from sqlalchemy import or_, and_

from ihome import sr, db
from ihome.models import Area, House, Facility, HouseImage, Order
from ihome.modules.api import api_blu
from ihome.utils import constants
from ihome.utils.common import login_required
from ihome.utils.constants import AREA_INFO_REDIS_EXPIRES, QINIU_DOMIN_PREFIX, HOUSE_LIST_PAGE_CAPACITY, \
    HOME_PAGE_MAX_HOUSES, HOME_PAGE_DATA_REDIS_EXPIRES
from ihome.utils.image_storage import storage_image
from ihome.utils.response_code import RET


# 我的发布列表
@api_blu.route('/user/houses')
@login_required
def get_user_house_list():
    """
    获取用户房屋列表
    1. 获取当前登录用户id
    2. 查询数据
    :return:
    """
    user_id = g.user_id

    try:
        houses = House.query.filter(House.user_id == user_id).all()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询数据失败")

    houses_dict = []
    for house in houses:
        houses_dict.append(house.to_basic_dict())
    return jsonify(errno=RET.OK, errmsg="OK", data=houses_dict)


# 获取地区信息
@api_blu.route("/areas")
def get_areas():
    """
    1. 查询出所有的城区
    2. 返回
    :return:
    """
    # 查询所有城区数据
    try:
        area = Area.query.all()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='查询数据异常')
    # 将城区对象数据列表转换成字典列表
    area_list = []
    for a in area if area else []:
        area_list.append(a.to_dict())

    # 组织返回数据
    # data = {
    #     'data':area_list
    # }
    # print(data)

    return jsonify(errno=RET.OK, errmsg='查询成功', data=area_list)


# 上传房屋图片
@api_blu.route("/houses/<int:house_id>/images", methods=['POST'])
@login_required
def upload_house_image(house_id):
    """
    1. 取到上传的图片
    2. 进行七牛云上传
    3. 将上传返回的图片地址存储
    4. 进行返回
    :return:
    """
    try:
        house_image = request.files.get("house_image").read()

    except Exception as e:
        current_app.logger.error(e)
        return jsonify(error=RET.PARAMERR, errmsg="参数错误")

    try:
        house = House.query.get(house_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(error=RET.DBERR, errmsg="查询房屋数据异常")

    if not house:
        return jsonify(errno=RET.DBERR, errmsg="未查询到指定房屋")

    try:
        url = storage_image(house_image)

    except Exception as e:
        current_app.logger.error(e)
        return jsonify(error=RET.DBERR, errmsg="查询用户数据异常")

    try:
        image = HouseImage()
        image.house_id = house_id
        image.url = url
        if not house.index_image_url:
            house.index_image_url = url
        db.session.add(image)
        db.session.commit()

    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(error=RET.DBERR, errmsg="保存房屋图片失败")
    return jsonify(errno=RET.OK, errmsg="保存成功", data={"url": constants.QINIU_DOMIN_PREFIX + url})


# 发布房源
@api_blu.route("/houses", methods=["POST"])
@login_required
def save_new_house():
    """
    1. 接收参数并且判空
    2. 将参数的数据保存到新创建house模型
    3. 保存house模型到数据库
    前端发送过来的json数据
    {
        "title":"",
        "price":"",
        "area_id":"1",
        "address":"",
        "room_count":"",
        "acreage":"",
        "unit":"",
        "capacity":"",
        "beds":"",
        "deposit":"",
        "min_days":"",
        "max_days":"",
        "facility":["7","8"]
    }
    :return:
    """
    param_dict = request.json

    title = param_dict.get("title")
    price = param_dict.get("price")
    area_id = param_dict.get("area_id")
    address = param_dict.get("address")
    room_count = param_dict.get("room_count")
    acreage = param_dict.get("acreage")
    unit = param_dict.get("unit")
    capacity = param_dict.get("capacity")
    beds = param_dict.get("beds")
    deposit = param_dict.get("deposit")
    min_days = param_dict.get("min_days")
    max_days = param_dict.get("max_days")
    facility = param_dict.get("facility")

    user_id = g.user_id

    if not user_id:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    if not all([title, price, area_id, address, room_count, acreage, unit, capacity, beds, deposit, min_days, max_days,
                facility]):
        # current_app.logger.error()
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")
    # images = param_dict.files.get("images")

    # try:
    #     image_name = storage_image(images.read())
    # except Exception as e:
    #     current_app.logger.error(e)
    #     return jsonify(errno=RET.DBERR, errmsg="上传图片数据到七牛云异常")
    #
    # # 图片名称没有值
    # if not image_name:
    #     return jsonify(errno=RET.DBERR, errmsg="上传图片数据到七牛云异常")

    try:
        price = int(float(price) * 100)
        deposit = int(float(deposit) * 100)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(error=RET.PARAMERR, errmsg="参数错误")

    house = House()
    house.user_id = user_id
    house.area_id = area_id
    house.title = title
    house.price = price
    house.address = address
    house.room_count = room_count
    house.acreage = acreage
    house.unit = unit
    house.capacity = capacity
    house.beds = beds
    house.deposit = deposit
    house.min_days = min_days
    house.max_days = max_days
    # house.images_url = constants.QINIU_DOMIN_PREFIX + image_name

    if facility:
        facilities = Facility.query.filter(Facility.id.in_(facility)).all()
        house.facilities = facilities

    try:
        db.session.add(house)
        db.session.commit()

    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(error=RET.DBERR, errmsg="保存房源信息异常")

    return jsonify(errno=RET.OK, errmsg="发布房源成功", data={'house_id': house.id})


# 房屋详情
@api_blu.route('/houses/<int:house_id>')
def get_house_detail(house_id):
    """
    1. 通过房屋id查询出房屋模型
    :param house_id:
    :return:
    """
    user_id = session.get('user_id', None)
    user = None
    if user_id:
        user = User.query.get(user_id)
    try:
        house = House.query.filter(House.id == house_id).first()
        # house = sr.get('house_id_%s'%house_id)
    except Exception as e:
        return jsonify(errno=RET.SESSIONERR, errmsg='查询数据错误')

    if not house:
        return jsonify(errno=RET.THIRDERR, errmsg='没有值')
    house_dict = house.to_full_dict() if house else None

    '''
    house
            acreage
            address
            beds
            capacity
            comments
            dfacilitieseposit
            deposit
            hid
            img_urls
            max_days
            min_days
            price
            room_count
            title
            unit
            user_avatar
            user_id
            user_name

    user_id
    '''

    data = {
        'house': house_dict,
        'user_id': user_id
    }

    return jsonify(errno=RET.OK, errmsg='查询OK', data=data)


# 获取首页展示内容
@api_blu.route('/houses/index')
def house_index():
    """
    获取首页房屋列表
    :return:
    """
    try:
        # 查询房屋订单倒序排序并显示5条
        houses = House.query.order_by(House.order_count.desc()).limit(constants.HOME_PAGE_MAX_HOUSES).all()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询数据异常")

    if not houses:
        return jsonify(errno=RET.NODATA, errmsg="该房子不存在")

        # 将查询到的房屋信息转换成字典数据，添加到定义的houses_list列表
    house_list = []
    for house in houses if houses else []:
        # 如果房屋未设置主图片，则跳过
        if not house.index_image_url:
            continue
        house_list.append(house.to_basic_dict())

    # 将列表数据转换从json格式的数据，并存到redis数据库中
    try:
        json_house = json.dumps(house_list)
        sr.setex("house_page_data", constants.HOME_PAGE_DATA_REDIS_EXPIRES, json_house)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="保存数据异常")

    # 因为第一次是不存在缓存数据的，所以我们在进入函数时，就先从redis中拿取数据
    try:
        ret = sr.get("house_page_data")
    except Exception as e:
        current_app.logger.error(e)
        ret = None

    if not ret:
        try:
            houses = House.query.order_by(House.order_count.desc()).limit(constants.HOME_PAGE_MAX_HOUSES).all()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询数据异常")

    ret = eval(ret)

    return jsonify(errno=RET.OK, errmsg="ok", data=ret)


# 搜索房屋/获取房屋列表
@api_blu.route('/houses')
def get_house_list():
    param_dict = request.args

    # 先设置一个初始的page和per_page
    page = 1
    per_page = 100

    # 设置一个列表来装排序条件
    sort_rule = House.acreage.desc()

    # 设置一个列表来装房屋查询条件
    house_filter_list = []

    # 2.根据参数情况处理不同的业务逻辑
    print(param_dict)

    if not (param_dict.get("aid") or param_dict.get("sd") or param_dict.get("ed")):

        # 没有任何查询条件时,快速的返回响应,提升用户体验
        try:
            paginate = House.query.filter(*house_filter_list).order_by(
                sort_rule).paginate(page, per_page, False)
            house_list = paginate.items
            total_page = paginate.pages

        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询房屋分页对象异常")

        # 将房屋分页对象列表转换为房屋分页对象字典列表
        house_dict_list = []
        for house in house_list if house_list else []:
            house_dict_list.append(house.to_basic_dict())
        data = {"houses": house_dict_list, "total_page": total_page}
        return jsonify(errno=RET.OK, errmsg="成功", data=data)

    if param_dict.get("p"):
        page = int(param_dict.get("p"))
    if param_dict.get("aid"):
        aid = param_dict.get("aid")
        house_filter_list.append(House.area_id == aid)

    if param_dict.get("sk"):
        if param_dict.get("sk") == "booking":
            sort_rule = House.order_count.desc()
        if param_dict.get("sk") == "price-inc":
            sort_rule = House.price.asc()
        if param_dict.get("sk") == "price-des":
            sort_rule = House.price.desc()

    if param_dict.get("sd") and param_dict.get("ed"):
        sd = param_dict.get("sd")
        ed = param_dict.get("ed")
        print(sd)
        print(ed)
        try:
            sd = datetime.datetime.strptime(sd, "%Y-%m-%d")
            ed = datetime.datetime.strptime(ed, "%Y-%m-%d")
            print(1)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.PARAMERR, errmsg="格式错误")
        try:
            if Order.query.all():
                # orders = Order.query.filter(sd <= Order.begin_date < ed or sd < Order.end_date < ed or (
                #         Order.begin_date <= sd and Order.end_date >= ed)).all()
                print(sd)
                print(ed)
                print(Order.begin_date)
                # 冲突订单
                orders = Order.query.filter(
                    or_(sd <= Order.begin_date, Order.begin_date < ed, sd < Order.end_date, Order.end_date < ed, and_(
                        Order.begin_date <= sd, Order.end_date >= ed))).all()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询房屋分页对象异常")
        # 有时间冲突的所有房屋id列表
        nagtive_house_id_list = [order.house_id for order in orders if orders]
        house_filter_list.append((House.id.notin_(nagtive_house_id_list)))

    elif param_dict.get("sd"):
        sd = param_dict.get("sd")
        try:
            sd = datetime.datetime.strptime(sd, "%Y-%m-%d")
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.PARAMERR, errmsg="格式错误")
        # 有时间冲突的所有订单列表(此时将Order.begin_date和Order.end_date固定)
        """
        1.sd < Order.begin_date  不冲突
        2.sd = Order.begin_date  冲突
        3.Order.begin_date < sd < Order.end_date 冲突
        4.sd = Order.end_date 不冲突
        5.sd > Order.end_date 不冲突
        """
        try:
            orders = Order.query.filter(Order.begin_date <= sd < Order.end_date).all()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询房屋分页对象异常")
            # 有时间冲突的所有房屋id列表
        nagtive_house_id_list = [order.house_id for order in orders if orders]
        house_filter_list.append((House.id.notin_(nagtive_house_id_list)))

    elif param_dict.get("ed"):
        ed = param_dict.get("ed")
        try:
            ed = datetime.datetime.strptime(ed, "%Y-%m-%d")
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.PARAMERR, errmsg="格式错误")
        # 有时间冲突的所有订单列表(此时将Order.begin_date和Order.end_date固定)
        """
        1.ed < Order.begin_date  不冲突
        2.ed = Order.begin_date  不冲突
        3.Order.begin_date < ed < Order.end_date 冲突
        4.ed = Order.end_date 不冲突
        5.ed > Order.end_date 不冲突
        """
        try:
            orders = Order.query.filter(Order.begin_date < ed < Order.end_date).all()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询房屋分页对象异常")
        nagtive_house_id_list = [order.house_id for order in orders if orders]
        house_filter_list.append((House.id.notin_(nagtive_house_id_list)))

    try:
        # print(*house_filter_list)
        # print(sort_rule)
        # paginate = House.query.filter(*house_filter_list).order_by(
        #     sort_rule).paginate(page, per_page, False)
        # print(paginate)
        # house_list = paginate.items
        # total_page = paginate.pages
        paginate = House.query.filter(*house_filter_list).order_by(
            sort_rule).paginate(page, per_page, False)
        house_list = paginate.items
        total_page = paginate.pages
    except Exception as e:
        print("error")
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询房屋分页对象异常")

    # 将房屋分页对象列表转换为房屋分页对象字典列表
    house_dict_list = []
    for house in house_list if house_list else []:
        house_dict_list.append(house.to_basic_dict())
    data = {"houses": house_dict_list, "total_page": total_page}
    return jsonify(errno=RET.OK, errmsg="成功", data=data)

