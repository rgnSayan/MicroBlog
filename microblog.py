from app import app, db
from app.models import User, Post
#import app {app here is the variable name} and the app in the "from app" is the directory name in which this python file is stored} 

#The following function in microblog.py creates a shell context that adds the database instance and models to the shell session:
@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Post': Post}

if __name__ == '__main__':
    app.run(debug=True)