#!/usr/bin/python3
# Red Eclipse proof-of-concept master server
# Isaac Smith - 2014-9-20

# Imports from the Python standard library
import hashlib
import random
from datetime import datetime, timedelta

# Imports from Bottle web framework
from bottle import get, post, request, run, static_file

# Imports from SQLAlchemy database library
import sqlalchemy
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref

# Constants for how long user and server keys last
KEY_LIFETIME = timedelta(hours=1)
SERVER_LIFETIME = timedelta(minutes=1)

# Connecting to the SQL DB, right now using an in-memory SQLite database but can easily be changed to MySQL, Postgres, etc
engine = create_engine('sqlite:///:memory:')
# Creates SQLAlchemy's Base class that all table classes inherit from
Base = declarative_base()

# Defining SQLAlchemy object-relational mappings, each class defines a table in the DB and maps the class to that table.
class User(Base):
    __tablename__ = 'Users'
    id = Column(Integer, primary_key = True)
    username = Column(String)
    password = Column(String)
    nickname = Column(String)
    email = Column(String)
    level = Column(Integer, default=0)
    # This creates a Python list containing the user's token keys, which are defined below
    keys = relationship('UserKey', backref = backref('Users', order_by = id), cascade="all, delete, delete-orphan")

    # This function overrides the Base class's init function, so when a new User is added then it's password is automatically hashed.
    def __init__(self, *args, **kwargs):
        # This calls the Base class's init function which does all the SQL heavy lifting.
        super(User, self).__init__(*args, **kwargs)
        # Hashing the password, this needs work to add a salt.
        self.password = hashlib.sha256(self.password.encode()).hexdigest()
        
    def check_password(self, password):
        hash = hashlib.sha256(password.encode()).hexdigest()
        print('debug login:', self.username, self.password, hash)
        if hash == self.password:
            return True
        else:
            return False
            
    def userdict(self):
        # Returns a dict containg info about the user, to be sent to clients.
        return {'username': self.username,
                'level': self.level}

# Defines the UserKeys table, which stores a token key each time a user logs in.
class UserKey(Base):
    __tablename__ = 'UserKeys'
    id = Column(Integer, primary_key = True)

    # The below two lines define how users and userkeys are related
    userid = Column(Integer, sqlalchemy.ForeignKey('Users.id'))
    user = relationship('User', backref = backref('UserKeys', order_by = id))
    
    key = Column(Integer)
    expires = Column(DateTime)
    
    def __init__(self, *args, **kwargs):
        super(UserKey, self).__init__(*args, **kwargs)

        self.expires = datetime.now() + KEY_LIFETIME

        # Creates a random 32-bit number, and makes sure its unique.
        while True:
            self.key = random.randint(0, 2**32-1)
            if not session.query(UserKey).filter(UserKey.key == self.key).first():
                break

    def expired(self):
        if datetime.now() > self.expires:
            return True
        else:
            return False
    
    def update(self):
        self.expires = datetime.now() + KEY_LIFETIME
    
class Server(Base):
    __tablename__ = 'Servers'
    id = Column(Integer, primary_key = True)
    name = Column(String)
    address = Column(String)
    port = Column(Integer)
    key = Column(Integer)
    expires = Column(DateTime)

    def __init__(self, *args, **kwargs):
        super(Server, self).__init__(*args, **kwargs)

        self.expires = datetime.now() + SERVER_LIFETIME

        while True:
            self.key = random.randint(0, 2**32-1)
            if not session.query(Server).filter(Server.key == self.key).first():
                break
                
    def expired(self):
        if datetime.now() > self.expires:
            return True
        else:
            return False
    
    def update(self):
        self.expires = datetime.now() + SERVER_LIFETIME

# This actually creates the tables defined above.
Base.metadata.create_all(engine)
# Creates a Session class
Session = sqlalchemy.orm.sessionmaker(bind=engine)
# Gets a Session instance, used to access the DB
session = Session()

# The below are Bottle functions that route URLs to code

# This serves up static files, eventually a "real" web server will do this instead.
@get('/static/<filename:path>')
def static_files(filename):
    return static_file(filename, root='static')

# Hands out the main page    
@get('/')
def main_page():
    return static_file('master.html', root='static')

# Gets a user dict from a userkey, or returns an error
@get('/user')
def get_user_from_key():
    key = request.query.get('key')
    if not key: return {'error': 'key not specified'}

    # The below is why I used SQLAlchemy, it's a lot simpler than writing SQL by hand.    
    userkey = session.query(UserKey).filter(UserKey.key == int(key)).first()
    if not userkey:
        return {'error': 'invalid key'}
        
    if userkey.expired():
        return {'error': 'key expired'}

    # Resets the userkey's expire property to KEY_LIFETIME in the future
    userkey.update()
    # Commits the updated userkey to the database
    session.commit()

    # Gets the user object from the userkey, then sends the user's dict to the client
    user = userkey.user
    return {'user': user.userdict()}

# Should be fairly obvious :D                   
@post('/user/login')
def login_user():
    username = request.forms.get('username')
    password = request.forms.get('password')
    
    user = session.query(User).filter(User.username == username).first()
    if not user: return {'error': 'login incorrect'}
    
    if not user.check_password(password):
        return {'error': 'login incorrect'}

    # Creates a new userkey and adds it to the user    
    userkey = UserKey()
    user.keys.append(userkey)
    session.commit()
    
    return {'key': userkey.key, 'user': user.userdict()}

# Also obvious.
@post('/user/logout')
def logout_user():
    key = request.forms.get('key')
    
    userkey = session.query(UserKey).filter(UserKey.key == key)
    if not userkey: return {'error': 'invalid key'}
    
    session.delete(userkey)
    session.commit()
    return {'success': True}
    
@post('/user/register')
def register_user():
    username = request.forms.get('username')
    password = request.forms.get('password')
    email = request.forms.get('email')
    
    if not username or not password or not email:
        return {'error': 'all forms must be specified'}
    
    # Creates the user and adds it to the session, then commits it to the DB
    user = User(username = username, password = password, email = email)
    session.add(user)
    session.commit()
    
    print('debug: created user', user.username, user.password, user.email)
    
    return {'success': True}

# Server list stuff, which will probably be managed by the current master server instead, so I won't bother commenting.
@get('/serverlist')
def list_servers():
    serverlist = []
    for server in session.query(Server):
        if server.expired():
            session.delete(server)
        else:
            serverlist.append((server.name, server.address))
            
    return {'serverlist': serverlist}
    
@post('/server/register')
def register_server():
    servername = request.forms.get('name')
    serveraddr = request.get('REMOTE_ADDR')
    serverport = request.forms.get('port')
    
    server = Server(name = servername, address = serveraddr, port = serverport)
    session.add(server)
    session.commit()

    return {'key': server.key}
    
@post('/server/heartbeat')
def server_heartbeat():
    key = request.forms.get('key')
    
    server = session.query(Server).filter(Server.key == int(key))
    if not server: return {'error': 'no such server'}
    
    server.update()
    return {'success': True}

# This detects if the program is being run directly (as opposed to being imported by another program) and starts the Bottle server
if __name__ == '__main__':
    run(host='0.0.0.0', port=8080)
