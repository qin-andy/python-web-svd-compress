import uuid, pickle, redis, os, time, re
from functools import wraps
from flask import Blueprint, request, session
from markupsafe import escape
from application.svd.ImageSVD import ImageSVD


api = Blueprint('api', __name__)
url = os.environ.get("REDIS_URL")
cache = None
if not url:
    cache = redis.Redis(host='redis', port=6379)
else:
    cache = redis.from_url(url)


EXPIRATION_TIME = 300 # In seconds


def assign_session(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = session.get('user_id')
        if user_id:
            return fn(*args, **kwargs)
        else:
            session['user_id'] = str(uuid.uuid4().hex)
            return fn(*args, **kwargs)
    return wrapper


def buildSVDJson(svd, svs):
    if svs > min(svd.width, svd.height):
        return "Singular values cannot exceed image size: " + str(svd.width) + "x" + str(svd.height), 400
    rgb = svd.get_reduced_image(svs);
    # rgb_list = rgb.tolist()
    return {"colors": str(rgb), "shape": (1, 1), "svs": svs}, 200


@api.route("/upload/image", methods=['GET', 'POST'])
@assign_session
def upload():
    print("Upload request receieved!")
    completeStart = time.time()
    svs = request.args.get("svs");
    if svs == None:
        svs = 10
    elif not svs.isnumeric():
        return "Invalid singular values count!", 400
    svs = int(svs)

    if request.method == 'POST':
        data = request.form
        img_64 = re.sub('^data:image/.+;base64,', '', data['data64'])
        if ((len(img_64) * 6) / 8000000) > 3:
            return "File too large: " + str((len(img_64) * 6) / 8000000), 400
        svd = ImageSVD(img_64, 64)

        start = time.time()
        cache.set(session.get("user_id"), pickle.dumps(svd))
        cache.expire(session.get("user_id"), EXPIRATION_TIME)
        print("Storing Upload SVD in Redis: " + str(time.time() - start))
        
        start = time.time()
        res, code = buildSVDJson(svd, svs)
        print("Building SVD Json: " + str(time.time() - start))
        print("Complete upload time:: " + str(time.time() - completeStart))
        return res, code
    else:
        return "<p>Image uploading endpoint</p>"


@api.route("/recalculate")
@assign_session
def recalculate_product():
    completeStart = time.time()
    svs = request.args.get("svs");

    if svs == None:
        svs = 10
    elif not svs.isnumeric():
        return "Invalid singular values count!", 400
    svs = int(svs)
    svd = None

    try:
        start = time.time()
        serialized_image_svd = cache.get(session.get("user_id"))
        svd = pickle.loads(serialized_image_svd)
        print("Fetching svd from redis: " + str(time.time() - start))
    except:
        return "Session timed out! Try recalculating!", 408
    start = time.time()
    res, code = buildSVDJson(svd, svs)
    print("Building SVD Json: " + str(time.time() - start))
    print("Complete recalculate time:: " + str(time.time() - completeStart))
    return res, code