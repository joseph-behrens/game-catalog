from sqlalchemy import (Column, Integer, String, ForeignKey,
                        DateTime, create_engine)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from passlib.apps import custom_app_context as pwd_context
import random
import string
import datetime
from itsdangerous import (TimedJSONWebSignatureSerializer as Serializer,
                          BadSignature, SignatureExpired)

Base = declarative_base()
secret_key = ''.join(
    random.choice(string.ascii_uppercase + string.digits)
    for x in range(32))


class User(Base):
    """Site users for logins."""

    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    email = Column(String)
    picture = Column(String(250))


class Image(Base):
    """Images used for logos of companies and games."""

    __tablename__ = 'image'
    id = Column(Integer, primary_key=True)
    url = Column(String)
    alt_text = Column(String)
    owner_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):
        """Use to return JSON formatted output."""
        return {
            'id': self.id,
            'url': self.url,
            'alt_text': self.alt_text
        }


class Rating(Base):
    """Game ratings from 1 to 5."""

    __tablename__ = 'rating'
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('game.id'))
    user_id = Column(Integer, ForeignKey('user.id'))
    score = Column(Integer)


class Company(Base):
    """Base class for companies of developers, publishers and manufacturers."""

    __tablename__ = 'company'
    id = Column(Integer, primary_key=True)
    name = Column(String(32))
    country = Column(String(32))
    image_id = Column(Integer, ForeignKey('image.id'))
    image = relationship(Image)
    owner_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)
    company_type = Column(String(32), nullable=False)
    __mapper_args__ = {'polymorphic_on': company_type}

    @property
    def serialize(self):
        """Use to return JSON formatted output."""
        return {
            'id': self.id,
            'name': self.name,
            'country': self.country,
            'company_type': self.company_type,
            'image_id': self.image_id
        }


class Manufacturer(Company):
    """Game manufacturers such as Nintendo, Sony, Microsoft, etc."""

    __tablename__ = 'manufacturer'
    id = Column(Integer, ForeignKey('company.id'), primary_key=True)
    year_founded = Column(String(4))
    __mapper_args__ = {'polymorphic_identity': 'manufacturer'}


class Publisher(Company):
    """Publishers such as Activision, EA, etc."""

    __tablename__ = 'publisher'
    id = Column(Integer, ForeignKey('company.id'), primary_key=True)
    __mapper_args__ = {'polymorphic_identity': 'publisher'}


class Developer(Company):
    """
    Game development companies such as Bethesda, BioWare, Valve, etc.
    
    Not currently used. But here as it is planned.
    """

    __tablename__ = 'developer'
    id = Column(Integer, ForeignKey('company.id'), primary_key=True)
    __mapper_args__ = {'polymorphic_identity': 'developer'}


class System(Base):
    """Game systems that games can run on, SNES, Playstation2, etc."""

    __tablename__ = 'system'
    id = Column(Integer, primary_key=True)
    manufacturer_id = Column(Integer, ForeignKey('manufacturer.id'))
    name = Column(String(32))
    description = Column(String)
    year_released = Column(Integer)
    image_id = Column(Integer, ForeignKey('image.id'))
    owner_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)
    image = relationship(Image)
    manufacturer = relationship(Manufacturer)

    @property
    def serialize(self):
        """Use to return JSON formatted output."""
        return {
            'id': self.id,
            'manufacturer_id': self.manufacturer_id,
            'name': self.name,
            'description': self.description,
            'year_released': self.year_released,
            'image_id': self.image_id
        }


class Role(Base):
    """Permission roles for users."""

    __tablename__ = 'role'
    id = Column(Integer, primary_key=True)
    name = Column(String(32))
    description = Column(String)


class UserRole(Base):
    """Roles assigned to users."""

    __tablename__ = 'user_role'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'))
    role_id = Column(Integer, ForeignKey('role.id'))
    user = relationship(User)
    role = relationship(Role)


class Game(Base):
    """Video game object."""

    __tablename__ = 'game'
    id = Column(Integer, primary_key=True)
    title = Column(String)
    description = Column(String)
    created_date = Column(DateTime, default=datetime.datetime.utcnow)
    edited_date = Column(DateTime)
    year_released = Column(Integer)
    average_rating = Column(String(3))
    image_id = Column(Integer, ForeignKey('image.id'))
    system_id = Column(Integer, ForeignKey('system.id'))
    owner_id = Column(Integer, ForeignKey('user.id'))
    publisher_id = Column(Integer, ForeignKey('publisher.id'))
    image = relationship(Image)
    system = relationship(System)
    owner = relationship(User, foreign_keys=[owner_id])
    publisher = relationship(Publisher)

    @property
    def serialize(self):
        """Use to return JSON formatted output."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'created_date': self.created_date,
            'edited_date': self.edited_date,
            'year_released': self.year_released,
            'average_rating': self.average_rating,
            'image_id': self.image_id,
            'system_id': self.system_id,
            'owner_id': self.owner_id,
            'publisher_id': self.publisher_id
        }


class GamePlatform(Base):
    """List of systems that specific games will run on."""

    __tablename__ = 'game_platform'
    id = Column(Integer, primary_key=True)
    system_id = Column(Integer, ForeignKey('system.id'))
    game_id = Column(Integer, ForeignKey('game.id'))
    relationship(System)
    relationship(Game)


engine = create_engine('sqlite:///data/games.db')
Base.metadata.create_all(engine)
