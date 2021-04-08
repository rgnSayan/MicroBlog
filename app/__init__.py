from flask import Flask     #Flask is the class name
from config import Config   #config is the name of the Python module config.py while Config is the class name
from flask_sqlalchemy import SQLAlchemy     #Database storage and usage
from flask_migrate import Migrate       #Flask-Migrate is an extension that handles SQLAlchemy database migrations for Flask applications 
from flask_login import LoginManager
import logging
from logging.handlers import SMTPHandler, RotatingFileHandler       #All I need to do to get emails sent out on errors is to add a SMTPHandler instance to the Flask logger object, which is app.logger
from flask_mail import Mail
from flask_bootstrap import Bootstrap
from flask_moment import Moment
import os

app = Flask(__name__)     #the app used here is the variable name
app.config.from_object(Config)
db = SQLAlchemy(app)        #I have added a db object that represents the database.
migrate = Migrate(app, db)   #I have added another object that represents the migration engine. 
login = LoginManager(app)
login.login_view = 'login'  #The 'login' value above is the function (or endpoint) name for the login view. In other words, the name you would use in a url_for() call to get the URL
mail = Mail(app)
bootstrap = Bootstrap(app)
moment = Moment(app)

#The code below creates a SMTPHandler instance, sets its level so that it only reports errors and not warnings, informational or debugging messages, and finally attaches it to the app.logger object from Flask.
if not app.debug:
    if app.config['MAIL_SERVER']:
        auth = None
        if app.config['MAIL_USERNAME'] or app.config['MAIL_PASSWORD']:
            auth = (app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        secure = None
        if app.config['MAIL_USE_TLS']:
            secure = ()
        mail_handler = SMTPHandler(mailhost=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),fromaddr='no-reply@' + app.config['MAIL_SERVER'],toaddrs=app.config['ADMINS'], subject='Microblog Failure',credentials=auth, secure=secure)
        mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(mail_handler)
        if not os.path.exists('logs'):
            os.mkdir('logs')

        file_handler = RotatingFileHandler('logs/microblog.log', maxBytes=10240,backupCount=10)     #I'm writing the log file with name microblog.log in a logs directory, which I create if it doesn't already exist . #The RotatingFileHandler class is nice because it rotates the logs, ensuring that the log files do not grow too large when the application runs for a long time. In this case I'm limiting the size of the log file to 10KB, and I'm keeping the last ten log files as backup.
        file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))         #The logging.Formatter class provides custom formatting for the log messages. Since these messages are going to a file, I want them to have as much information as possible. So I'm using a format that includes the timestamp, the logging level, the message and the source file and line number from where the log entry originated.
        file_handler.setLevel(logging.INFO)     #To make the logging more useful, I'm also lowering the logging level to the INFO category, both in the application logger and the file logger handler. In case you are not familiar with the logging categories, they are DEBUG, INFO, WARNING, ERROR and CRITICAL in increasing order of severity.
        app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info('Microblog startup')

from app import routes, models, errors
#the app here is the directory name in which this python file is stored , models is the new module which defines the structure of the database