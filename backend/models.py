from sqlalchemy import Column, Integer, String
from database import Base


class Order(Base):

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)

    client = Column(String)

    phone = Column(String)

    amount = Column(String)

    status = Column(String)


class User(Base):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    username = Column(String, unique=True)

    password = Column(String)
    role = Column(String)