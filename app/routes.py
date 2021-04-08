from flask import render_template, flash, redirect, url_for, request
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.urls import url_parse
from app import app, db
from app.forms import LoginForm, RegistrationForm, EditProfileForm, EmptyForm, PostForm, ResetPasswordRequestForm
from app.models import User, Post
from datetime import datetime
from app.email import send_password_reset_email


@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@login_required     #The way Flask-Login protects a view function against anonymous users is with a decorator called @login_required. When you add this decorator to a view function below the @app.route decorators from Flask, the function becomes protected and will not allow access to users that are not authenticated
def index():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(body=form.post.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('Your post is now live!')
        return redirect(url_for('index'))
    # user = {'username': 'Shivansh Singh'}
    posts = [
        {
            'author': {'username': 'John'},
            'body': 'Beautiful day in Portland!'
        },
        {
            'author': {'username': 'Susan'},
            'body': 'The Avengers movie was so cool!'
        }
    ]
    page = request.args.get('page', 1, type=int)
    # The followed_posts method of the User class returns a SQLAlchemy query object that is configured to grab the posts the user is interested in from the database. Calling all() on this query triggers its execution, with the return value being a list with all the results. So I end up with a structure that is very much alike the one with fake posts that I have been using until now. It's so close that the template does not even need to change.
    posts = current_user.followed_posts().paginate(page, app.config['POSTS_PER_PAGE'], False)       # The POSTS_PER_PAGE configuration item that determines the page size is accessed through the app.config object.
    next_url = url_for('index', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('index', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template('index.html', title='Home', form=form, posts=posts.items, next_url=next_url, prev_url=prev_url)

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Edit Profile', form=form)


#If you are wondering why there is no db.session.add() before the commit, consider that when you reference current_user, Flask-Login will invoke the user loader callback function, which will run a database query that will put the target user in the database session. So you can add the user again in this function, but it is not necessary because it is already there.
@app.before_request     #It register the decorated function to be executed right before the view function.This is extremely useful because now I can insert code that I want to execute before any view function in the application, and I can have it in a single place.
def before_request():
    if current_user.is_authenticated:       #The implementation simply checks if the current_user is logged in
        current_user.last_seen = datetime.utcnow()      # In the case if the user is logged in , sets the last_seen field to the current time. 
        db.session.commit()     #To commit the database session, so that the change made above is written to the database.


@app.route('/login', methods=['GET', 'POST'])        #methods argument in the route decorator tells Flask that this view function accepts GET and POST requests, overriding the default, which is to accept only GET requests
#POST requests are typically used when the browser submits form data to the server (in reality GET requests can also be used for this purpose, but it is not a recommended practice)
def login():
    #The 2 lines below deals with a weird situation . Imagine you have a user that is logged in, and the user navigates to the /login URL of your application. Clearly that is a mistake
    if current_user.is_authenticated:       #to check if the user is logged in or not. When the user is already logged in, I just redirect to the index page.
        return redirect('/index')
    form = LoginForm()
    if form.validate_on_submit():       #The form.validate_on_submit() method does all the form processing work. When the browser sends the GET request to receive the web page with the form, this method is going to return False, so in that case the function skips the if statement and goes directly to render the template in the last line of the function
        user = User.query.filter_by(username=form.username.data).first()    #The result of filter_by() is a query that only includes the objects that have a matching username . Since I know there is only going to be one or zero results, I complete the query by calling first(), which will return the user object if it exists, or None if it does not
        if user is None or not user.check_password(form.password.data):     #If I got a match for the username that was provided, I can next check if the password that also came with the form is valid. This is done by invoking the check_password() method
            flash('Invalid username or password')
            return redirect(url_for('login'))      #redirect() function instructs the client web browser to automatically navigate to a different page, given as an argument. This view function uses it to redirect the user to the index page of the application
        login_user(user, remember=form.remember_me.data)
        # Right after the user is logged in by calling Flask-Login's login_user() function, the value of the next query string argument is obtained. Flask provides a request variable that contains all the information that the client sent with the request. In particular, the request.args attribute exposes the contents of the query string in a friendly dictionary format. There are actually three possible cases that need to be considered to determine where to redirect after a successful login:
        # If the login URL does not have a next argument, then the user is redirected to the index page.
        # If the login URL includes a next argument that is set to a relative path (or in other words, a URL without the domain portion), then the user is redirected to that URL.
        # If the login URL includes a next argument that is set to a full URL that includes a domain name, then the user is redirected to the index page.
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
        # flash('Login requested for user {},remember_me={}'.format(form.username.data, form.remember_me.data))       #The flash() function is a useful way to show a message to the user
        # return redirect(url_for('index'))      #redirect() function instructs the client web browser to automatically navigate to a different page, given as an argument. This view function uses it to redirect the user to the index page of the application
    return render_template('login.html', title='Sign In', form=form)        #form=form is simply passing the form object to the template with the name form


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

#I have a dynamic component in it, which is indicated as the <username> URL component that is surrounded by < and >. When a route has a dynamic component, Flask will accept any text in that portion of the URL, and will invoke the view function with the actual text as an argument. For example, if the client browser requests URL /user/susan, the view function is going to be called with the argument username set to 'susan'. This view function is only going to be accessible to logged in users, so I have added the @login_required decorator from Flask-Login.
@app.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()       #It is checking whether the  username by which you are trying to log in exists in the database or not and if it exists then it will be simply logged in but in case if it does not exists in the database then a error 404 will be displayed
    page = request.args.get('page', 1, type=int)
    posts = user.posts.order_by(Post.timestamp.desc()).paginate(page, app.config['POSTS_PER_PAGE'], False)
    next_url = url_for('user', username=user.username, page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('user', username=user.username, page=posts.prev_num) \
        if posts.has_prev else None
    form = EmptyForm()
    return render_template('user.html', user=user, posts=posts.items, next_url=next_url, prev_url=prev_url, form=form)


@app.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=username).first()
        if user is None:
            flash('User {} not found.'.format(username))
            return redirect(url_for('index'))
        if user == current_user:
            flash('You cannot follow yourself!')
            return redirect(url_for('user', username=username))
        current_user.follow(user)
        db.session.commit()
        flash('You are following {}!'.format(username))
        return redirect(url_for('user', username=username))
    else:
        return redirect(url_for('index'))


@app.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=username).first()
        if user is None:
            flash('User {} not found.'.format(username))
            return redirect(url_for('index'))
        if user == current_user:
            flash('You cannot unfollow yourself!')
            return redirect(url_for('user', username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash('You are not following {}.'.format(username))
        return redirect(url_for('user', username=username))
    else:
        return redirect(url_for('index'))


# If the current page is at one of the ends of the collection of posts, then the has_next or has_prev attributes of the Pagination object will be False, and in that case the link in that direction will be set to None.
@app.route('/explore')
@login_required
def explore():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.timestamp.desc()).paginate(page, app.config['POSTS_PER_PAGE'], False)
    next_url = url_for('explore', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('explore', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template('index.html', title='Explore', posts=posts.items, next_url=next_url, prev_url=prev_url)      #  But one difference with the main page is that in the explore page I do not want to have a form to write blog posts, so in this view function I did not include the form argument in the template call.


@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash('Check your email for the instructions to reset your password')
        return redirect(url_for('login'))
    return render_template('reset_password_request.html',
                           title='Reset Password', form=form)

# In this view function I first make sure the user is not logged in, and then I determine who the user is by invoking the token verification method in the User class. This method returns the user if the token is valid, or None if not. If the token is invalid I redirect to the home page.
# If the token is valid, then I present the user with a second form, in which the new password is requested. This form is processed in a way similar to previous forms, and as a result of a valid form submission, I invoke the set_password() method of User to change the password, and then redirect to the login page, where the user can now login.
@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset.')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)