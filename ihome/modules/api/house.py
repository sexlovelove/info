import datetime

from flask import current_app, jsonify, request, g, session
from ihome import sr, db
from ihome.models import Area, House, Facility, HouseImage, Order, User
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
    # """


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
    try:
        area = Area.query.all()
    except Exception as e:
        return jsonify(errno=RET.DBERR, errmsg='查询数据异常')
        # 将城区对象数据列表转换成字典列表
    area_list = []
    for a in area if area else []:
        area_list.append(a.to_dict())

    # 组织返回数据
    data = {
        'areas': area_list
    }

    return jsonify(errno=RET.OK, errmsg='查询成功', data=data)


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
    user_id = g.user_id
    if not user_id:
        return jsonify(errno=RET.NODATA, errmsg="未查询到数据")

    house_id = request.args.get(house_id)
    if not house_id:
        return jsonify(errno=RET.NODATA, errmsg="未查询到数据")
    house = House.query.get(house_id)

    # 取到上传的图片
    index_image = request.files.get("index_image")
    if index_image:
        try:
            index_image = index_image.read()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.PARAMERR, errmsg="参数有误")

        # 2. 将标题图片上传到七牛
        try:
            key = storage_image(index_image)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.THIRDERR, errmsg="上传图片错误")

        # 3.将上传返回的图片地址存储
        house.index_image_url = constants.QINIU_DOMIN_PREFIX + key

        # 4进行返回
        data = {"url": house.index_image_url}
        return jsonify(data=data, errno=RET.OK, errmsg="OK")


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



    param_dict=request.json

    title=param_dict.get("title")
    price=param_dict.get("price")
    area_id=param_dict.get("area_id")
    address=param_dict.get("address")
    room_count=param_dict.get("room_count")
    acreage=param_dict.get("acreage")
    unit=param_dict.get("unit")
    capacity=param_dict.get("capacity")
    beds=param_dict.get("beds")
    deposit=param_dict.get("deposit")
    min_days=param_dict.get("min_days")
    max_days=param_dict.get("max_days")
    facility=param_dict.get("facility")
    images=param_dict.get("images")
    user_id = g.user_id


    if not user_id:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    if not all([title,price,area_id,address,room_count,acreage,unit,capacity,beds,deposit,min_days,max_days,facility,images]):

        current_app.logger.error()
        return jsonify(errno=RET.PARAMERR,errmsg="参数不足")

    try:
        image_name = storage_image(images.read())
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="上传图片数据到七牛云异常")

    # 图片名称没有值
    if not image_name:
        return jsonify(errno=RET.DBERR, errmsg="上传图片数据到七牛云异常")

    try:
        price=int(float(price)*100)
        deposit=int(float(deposit)*100)


    except Exception as e:
        current_app.logger.error(e)
        return jsonify(error=RET.PARAMERR,errmsg="参数错误")



    house=House()
    house.user_id=user_id
    house.area_id=area_id
    house.title=title
    house.price=price
    house.address=address
    house.room_count=room_count
    house.acreage=acreage
    house.unit=unit
    house.capacity=capacity
    house.beds=beds
    house.deposit=deposit
    house.min_days=min_days
    house.max_days=max_days
    house.images_url=constants.QINIU_DOMIN_PREFIX+image_name

    if facility:
        facilities = Facility.query.filter(Facility.id.in_(facility)).all()
        house.facilities = facilities

    try:
        db.session.add(house)
        db.session.commit()

    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(error=RET.DBERR,errmsg="保存房源信息异常")

    return jsonify(errno=RET.OK,errmsg="发布房源成功",data={'house_id':house.id})





# 房屋详情
@api_blu.route('/houses/<int:house_id>')
def get_house_detail(house_id):
    """
    1. 通过房屋id查询出房屋模型
    :param house_id:
    :return:
    """
    user_id = session.get('user_id', None)

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
@login_required
def house_index():
    """
    获取首页房屋列表
    :return:
    """

    pass


# 搜索房屋/获取房屋列表
@api_blu.route('/houses')
def get_house_list():
    pass
