from datetime import datetime
from app import db, login, app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from hashlib import md5
from time import time
import jwt

followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)


#The User class created above inherits from db.Model, a base class for all models from Flask-SQLAlchemy
class User(UserMixin, db.Model):
    # This class defines several fields as class variables
    # Fields are created as instances of the db.Column class, which takes the field type as an argument, plus other optional arguments that, for example, allow me to indicate which fields are unique and indexed, which is important so that database searches are efficient
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    posts = db.relationship('Post', backref='author', lazy='dynamic')
    about_me = db.Column(db.String(140))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

    # The avatar() method returns the URL of the user's avatar image, scaled to the requested size in pixels. For users that don't have an avatar registered, an "identicon" image will be generated
    def avatar(self, size):
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return 'https://www.gravatar.com/avatar/{}?d=identicon&s={}'.format(
            digest, size)

    # The __repr__ method tells Python how to print objects of this class, which is going to be useful for debugging
    def __repr__(self):
        return '<User {}>'.format(self.username)

    # With these two methods in place, a user object is now able to do secure password verification, without the need to ever store original passwords.
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # db.relationship function is used to define the relationship in the model class. This relationship links User instances to other User instances, so as a convention let's say that for a pair of users linked by this relationship
    # 'User' is the right side entity of the relationship (the left side entity is the parent class). Since this is a self-referential relationship, I have to use the same class on both sides.
    # secondary configures the association table that is used for this relationship, which I defined right above this class.
    # primaryjoin indicates the condition that links the left side entity (the follower user) with the association table. The join condition for the left side of the relationship is the user ID matching the follower_id field of the association table. The followers.c.follower_id expression references the follower_id column of the association table.
    # secondaryjoin indicates the condition that links the right side entity (the followed user) with the association table. This condition is similar to the one for primaryjoin, with the only difference that now I'm using followed_id, which is the other foreign key in the association table.
    # backref defines how this relationship will be accessed from the right side entity. From the left side, the relationship is named followed, so from the right side I am going to use the name followers to represent all the left side users that are linked to the target user in the right side. The additional lazy argument indicates the execution mode for this query. A mode of dynamic sets up the query to not run until specifically requested, which is also how I set up the posts one-to-many relationship.
    # lazy is similar to the parameter of the same name in the backref, but this one applies to the left side query instead of the right side.
    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic')

    # The follow() and unfollow() methods use the append() and remove() methods of the relationship object as I have shown above, but before they touch the relationship they use the is_following() supporting method to make sure the requested action makes sense. 
    # For example, if I ask user1 to follow user2, but it turns out that this following relationship already exists in the database, I do not want to add a duplicate. The same logic can be applied to unfollowing.
    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(followers.c.followed_id == user.id).count() > 0

    # Chapter 8
    # There are three main sections designed by the join(), filter() and order_by() methods of the SQLAlchemy query object:
    # Post.query.join(...).filter(...).order_by(...)
    # The join operation gave me a list of all the posts that are followed by some user
    # The condition that I used says that the followed_id field of the followers table must be equal to the user_id of the posts table. To perform this merge, the database will take each record from the posts table (the left side of the join) and append any records from the followers table (the right side of the join) that match the condition. If multiple records in followers match the condition, then the post entry will be repeated for each. If for a given post there is no match in followers, then that post record is not part of the join.
    # I'm only interested in a subset of this list, the posts followed by a single user, so I need trim all the entries I don't need, which I can do with a filter() call
    # Since this query is in a method of class User, the self.id expression refers to the user ID of the user I'm interested in. The filter() call selects the items in the joined table that have the follower_id column set to this user, which in other words means that I'm keeping only the entries that have this user as a follower.
    # The final step of the process is to sort the results. The part of the query that does that says : order_by(Post.timestamp.desc())
    def followed_posts(self):
        followed = Post.query.join(
            followers, (followers.c.followed_id == Post.user_id)).filter(
                followers.c.follower_id == self.id)
        own = Post.query.filter_by(user_id=self.id)
        return followed.union(own).order_by(Post.timestamp.desc())

    # The payload that I'm going to use for the password reset tokens is going to have the format {'reset_password': user_id, 'exp': token_expiration}. The exp field is standard for JWTs and if present it indicates an expiration time for the token. If a token has a valid signature, but it is past its expiration timestamp, then it will also be considered invalid. For the password reset feature, I'm going to give these tokens 60 minutes of life.
    # The get_reset_password_token() function returns a JWT token as a string, which is generated directly by the jwt.encode() function.
    def get_reset_passwords(self, expires_in=3600):
        return jwt.encode({'reset_password': self.id, 'exp': time() + expires_in}, app.config['SECRET_KEY'], algorithm='HS256')

    # When the user clicks on the emailed link, the token is going to be sent back to the application as part of the URL, and the first thing the view function that handles this URL will do is to verify it. If the signature is valid, then the user can be identified by the ID stored in the payload. Once the user's identity is known, the application can ask for a new password and set it on the user's account.
    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])['reset_password']
        except:
            return
        return User.query.get(id)

@login.user_loader
def load_user(id):      #The id that Flask-Login passes to the function as an argument is going to be a string, so databases that use numeric IDs need to convert the string to integer
    return User.query.get(int(id))


#Post class will represent blog posts written by users
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140))
    #When you pass a function as a default, SQLAlchemy will set the field to the value of calling that function (note that I did not include the () after utcnow, so I'm passing the function itself, and not the result of calling it).
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    #The timestamp field is going to be indexed, which is useful if you want to retrieve posts in chronological order.
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))       #user part is the name of the database table for the model

    def __repr__(self):
        return '<Post {}>'.format(self.body)