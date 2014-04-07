from sqlalchemy import create_engine, orm, Column, Integer, String, Boolean
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine('sqlite:///ircpuzzles.db')
session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()
Base.query = session.query_property()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    account = Column(String)
    confirmed = Column(Boolean)
    password = Column(String)
    confirmation_code = Column(String)

    def __repr__(self):
        return "<User(account='%s', confirmed='%s')>" % (self.account, str(self.confirmed))



Base.metadata.create_all(engine)