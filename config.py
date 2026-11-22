class Config:
    SECRET_KEY = "change-this-later"
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:@localhost/sa_brothers"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class Config:
    SECRET_KEY = "इथे वरची लांब ओळ पेस्ट करा"
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:@127.0.0.1/sa_brothers"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_SAMESITE = "Lax"