from flask import Flask, request, redirect, render_template, session, flash
from flask_sqlalchemy import SQLAlchemy
from hashutils import make_pw_hash, check_pw_hash
from datetime import datetime

app = Flask(__name__)
app.config['DEBUG'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://blogz:yes@localhost:8889/blogz'
app.config['SQLALCHEMY_ECHO'] = True
app.config['POSTS_PER_PAGE'] = 5
app.secret_key = 'nkklhjS%HRgt'
db = SQLAlchemy(app)


# Blog class
class Blog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(360))
    body = db.Column(db.Text)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created = db.Column(db.DateTime)

    def __init__(self, title, body, owner, created=None):
        self.title = title
        self.body = body
        self.owner = owner
        if created is None:
            created = datetime.utcnow()
        self.date = datetime.utcnow()
        self.created = created;


# User class
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True)
    pw_hash = db.Column(db.String(120))
    blogs = db.relationship('Blog', backref='owner')

    def __init__(self, username, password):
        self.username = username
        self.pw_hash = make_pw_hash(password)


# checks that user is logged in before they can post a new review
# not a route handler, runs before every request
@app.before_request
def require_login():
    # list of routes where login isn't required, using endpoints.
    # Endpoint is the name of the *function* for that route handler,
    # not the url. For example, 'show_blog' instead of '/blog'
    allowed_routes = ['index', 'login', 'signup', 'show_blog']

    # If the user is trying to go to a restricted route(not in allowed_routes),
    # check if they are logged in. If they're not logged in, redirect them to do so.
    if request.endpoint not in allowed_routes and 'username' not in session:
        flash("Please log into your account.")
        return redirect('/login')


# Index route
@app.route('/')
def index():
    users = User.query.all()
    return render_template('index.html', title="Blogz", users=users)


# Login route handler
@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        # makes sure username/password are correct, if they are, log them in and redirect to new review
        if user and check_pw_hash(password, user.pw_hash):
            session['username'] = username
            flash('Logged in')
            return redirect('/newpost')
        # if username doesn't exist, flash error and render login
        if not user:
            flash('Username does not exist', 'error')
            return render_template('login.html')
        # if password is wrong, flash error and re-render login with username saved
        else:
            flash('Password is incorrect.', 'error')
            return render_template('login.html', username=username)

    return render_template('login.html')


# Registration route handler, creates new row in User database and redirects
@app.route('/signup', methods=['POST', 'GET'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        verify = request.form['verify']

        username_error = ''
        password_error = ''
        verify_error = ''
        space = ' '

        # make sure username doesn't already exist, pass in error if it does.
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            username_error = "Username already exists, please choose a new one."
            password = ''
            verify = ''

        # validate username
        if len(username) < 3 or len(username) > 20 or username.count(space) != 0:
            username_error = 'Please enter a valid username (3-20 characters, no spaces).'
            password = ''
            verify = ''

        # validate password
        if len(password) < 3 or len(password) > 20 or password.count(space) != 0:
            password_error = "Please enter a valid password (3-20 characters, no spaces)."
            password = ''
            verify = ''

        # validate verify
        if verify != password:
            verify_error = "Password verification must match."
            password = ''
            verify = ''

        # if no errors, create new user and log them in
        if not username_error and not password_error and not verify_error:
            new_user = User(username, password)
            db.session.add(new_user)
            db.session.commit()
            session['username'] = username
            flash("Account created!")
            return redirect('/newpost')

        # if there is an error, re-render the template with relevant error messages.
        else:
            flash("Account could not be created, see error message below.", 'error')
            return render_template('signup.html',
                                   title="Sign Up For An Account on Blogz!",
                                   username=username, username_error=username_error,
                                   password=password, password_error=password_error,
                                   verify=verify, verify_error=verify_error)

    return render_template('signup.html')


# Logout route, deletes session and redirects user to /blog
@app.route('/logout')
def logout():
    del session['username']
    flash("Logged out!")
    return redirect('/blog')


# Blog route, renders a view of blog post/s
@app.route('/blog', methods=['POST', 'GET'])
def show_blog():
    # view a single post, url is /blog?id=3
    if 'id' in request.args:
        blog_id = request.args.get('id')
        blogs = Blog.query.filter_by(id=blog_id)
        return render_template('post.html', blogs=blogs)

    # page = requests.args.get('page', 1, type=int)
    # view all blogs for one user, url is /blog?user=brandy
    elif 'user' in request.args:
        author = request.args.get('user')
        user = User.query.filter_by(username=author).first()
        blogs = user.blogs
        return render_template('singleUser.html', author=author, user=user, blogs=blogs)

    # view all blogs by all users, url is just /blog
    else:
        blogs = Blog.query.order_by('created desc').all()
        return render_template('blog.html', title="Build a Blog!", blogs=blogs)


# New post route,
@app.route('/newpost', methods=['POST', 'GET'])
def create_new_post():
    # Renders blank blog post form
    if request.method == 'GET':
        return render_template('new_post.html', title="New Blog Entry")

    # Validates new blog post and sends to Blogs database
    if request.method == 'POST':
        # Retrieve the logged-in user's username
        user = User.query.filter_by(username=session['username']).first()
        # Retrieve blog content from the form
        blog_title = request.form['title']
        blog_body = request.form['body']
        new_blog = Blog(blog_title, blog_body, user)
        # set errors blank before they're checked
        title_error = ''
        body_error = ''

        # Check errors/generate error messages
        if len(blog_title) == 0:
            title_error = "Please enter a title for your new post."
        if len(blog_body) == 0:
            body_error = "Please enter text for your new post."

        # if everything is in order, add new blog to Blogs table and redirect to the new post
        if not title_error and not body_error:
            db.session.add(new_blog)
            db.session.commit()
            return redirect('/blog?id={}'.format(new_blog.id))

        # if something's wrong, render template with errors shown
        else:
            blogs = Blog.query.all()
            return render_template('new_post.html', title="Build a Blog!", blogs=blogs,
                                   blog_title=blog_title, title_error=title_error,
                                   blog_body=blog_body, body_error=body_error)


if __name__ == '__main__':
    app.run()