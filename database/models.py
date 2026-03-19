from sqlalchemy import Column, Integer, String, Boolean, BigInteger, DateTime, func, Table, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

# Таблица связи пользователей с интересами (многие ко многим)
user_interests = Table(
    'user_interests', Base.metadata,
    Column('user_id', BigInteger, ForeignKey('users.id'), primary_key=True),
    Column('interest_id', Integer, ForeignKey('interests.id'), primary_key=True)
)

# Модель интереса (хобби/тематика)
class Interest(Base):
    __tablename__ = 'interests'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    emoji = Column(String)

    def __repr__(self):
        return f"<Interest(id={self.id}, name='{self.name}')>"

# Модель пользователя
class User(Base):
    __tablename__ = 'users'
    id = Column(BigInteger, primary_key=True)
    username = Column(String)
    like = Column(Boolean)
    status = Column(Integer)
    gender = Column(String)
    experience = Column(Integer, default=0)
    level = Column(Integer, default=1)
    interests = relationship("Interest", secondary=user_interests, backref="users")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', status={self.status})>"

# Модель контакта (взаимный лайк)
class Contact(Base):
    __tablename__ = 'contacts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger)
    contact_id = Column(BigInteger)
    contact_username = Column(String)
    created_at = Column(DateTime, default=func.now())

    def __repr__(self):
        return f"<Contact(user_id={self.user_id}, contact_id={self.contact_id})>"

# Статистика пользователя
class UserStats(Base):
    __tablename__ = 'user_stats'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger)
    matches_count = Column(Integer, default=0)
    likes_given = Column(Integer, default=0)
    likes_received = Column(Integer, default=0)
    messages_sent = Column(Integer, default=0)
    last_active = Column(DateTime, default=func.now())
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)

    def __repr__(self):
        return f"<UserStats(user_id={self.user_id}, matches={self.matches_count})>"

# Сессия чата между двумя пользователями
class ChatSession(Base):
    __tablename__ = 'chat_sessions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user1_id = Column(BigInteger)
    user2_id = Column(BigInteger)
    start_time = Column(DateTime, default=func.now())
    end_time = Column(DateTime)
    common_interests = Column(String)

    def __repr__(self):
        return f"<ChatSession(user1={self.user1_id}, user2={self.user2_id})>"

# Запись о взаимном совпадении пользователей
class UserMatch(Base):
    __tablename__ = 'user_matches'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger)
    matched_user_id = Column(BigInteger)
    match_time = Column(DateTime, default=func.now())
    common_interests_count = Column(Integer, default=0)

    def __repr__(self):
        return f"<UserMatch(user={self.user_id}, matched={self.matched_user_id})>"
