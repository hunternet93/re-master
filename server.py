#!/usr/bin/python3
import hashlib
import random
from datetime import datetime, timedelta

from bottle import get, post, request, run, static_file

import sqlalchemy
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref

KEY_LIFETIME = timedelta(hours=1)
SERVER_LIFETIME = timedelta(minutes=1)

engine = create_engine('sqlite:///:memory:')
Base = declarative_base()

class User(Base):
    __tablename__ = 'Users'
    id = Column(Integer, primary_key = True)
    username = Column(String)
    password = Column(String)
    nickname = Column(String)
    email = Column(String)
    level = Column(Integer, default=0)
    keys = relationship('UserKey', backref = backref('Users', order_by = id), cascade="all, delete, delete-orphan")
    
    def __init__(self, *args, **kwargs):
        super(User, self).__init__(*args, **kwargs)
        self.password = hashlib.sha256(self.password.encode()).hexdigest()
        
    def check_password(self, password):
        hash = hashlib.sha256(password.encode()).hexdigest()
        print('debug login:', self.username, self.password, hash)
        if hash == self.password:
            return True
        else:
            return False
            
    def userdict(self):
        return {'username': self.username,
                'level': self.level}
    
class UserKey(Base):
    __tablename__ = 'UserKeys'
    id = Column(Integer, primary_key = True)
    userid = Column(Integer, sqlalchemy.ForeignKey('Users.id'))
    user = relationship('User', backref = backref('UserKeys', order_by = id))
    key = Column(Integer)
    expires = Column(DateTime)
    
    def __init__(self, *args, **kwargs):
        super(UserKey, self).__init__(*args, **kwargs)

        self.expires = datetime.now() + KEY_LIFETIME

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
        
Base.metadata.create_all(engine)
Session = sqlalchemy.orm.sessionmaker(bind=engine)
session = Session()

@get('/static/<filename:path>')
def static_files(filename):
    return static_file(filename, root='static')
    
@get('/')
def main_page():
    return static_file('master.html', root='static')

@get('/user')
def get_user_from_key():
    key = request.query.get('key')
    if not key: return {'error': 'key not specified'}
    
    userkey = session.query(UserKey).filter(UserKey.key == int(key)).first()
    if not userkey:
        return {'error': 'invalid key'}
        
    if userkey.expired():
        return {'error': 'key expired'}

    userkey.update()
    session.commit()

    user = userkey.user
    return {'user': user.userdict()}
                   
@post('/user/login')
def login_user():
    username = request.forms.get('username')
    password = request.forms.get('password')
    
    user = session.query(User).filter(User.username == username).first()
    if not user: return {'error': 'login incorrect'}
    
    if not user.check_password(password):
        return {'error': 'login incorrect'}
    
    userkey = UserKey()
    user.keys.append(userkey)
    session.commit()
    for k in user.keys: print(k.key)
    return {'key': userkey.key, 'user': user.userdict()}
    
@post('/user/logout')
def logout_user():
    key = request.forms.get('key')
    
    userkey = session.query(UserKey).filter(UserKey.key == key)
    if not userkey: return {'error': 'invalid key'}
    
    session.delete(userkey)
    return {'success': True}
    
@post('/user/register')
def register_user():
    username = request.forms.get('username')
    password = request.forms.get('password')
    email = request.forms.get('email')
    
    if not username or not password or not email:
        return {'error': 'all forms must be specified'}
    
    user = User(username = username, password = password, email = email)
    session.add(user)
    session.commit()
    
    print('debug: created user', user.username, user.password, user.email)
    
    return {'success': True}
    
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
    
if __name__ == '__main__':
    run(host='0.0.0.0', port=8080)
