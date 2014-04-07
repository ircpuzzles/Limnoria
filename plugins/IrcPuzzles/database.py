from sqlalchemy import create_engine, orm, Column, Integer, String, Boolean, Base
from sqlalchemy.orm import sessionmaker
engine = create_engine('sqlite:///ircpuzzles.db')

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    account = Column(String)
    confirmed = Column(Boolean)
    password = Column(String)
    confirmation_code = Column(String)

    def __repr__(self):
        return "<User(account='%s', confirmed='%s')>" % (self.account, str(self.confirmed))


session = sessionmaker(bind=engine)
Base.metadata.create_all(engine)