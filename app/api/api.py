from flask import (Flask, render_template, request, redirect,
                   jsonify, url_for, flash, make_response,
                   Blueprint)
from sqlalchemy import create_engine, asc, desc
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from models import (Base, Image, Rating, Company, Manufacturer, Publisher,
                    Developer, System, User, Role, UserRole, Game,
                    GamePlatform, secret_key)


api = Blueprint('api', 'api', url_prefix='/api/v1')


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    engine = create_engine('sqlite:///data/games.db')
    Base.metadata.bind = engine
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    try:
        yield session
        session.commit()
    except:  # noqa: E722
        session.rollback()
        raise
    finally:
        session.close()


@api.route('/games')
def gamesList():
    """Retrieve JSON of all game objects."""
    with session_scope() as session:
        games = session.query(Game).all()
        return jsonify(games=[game.serialize for game in games])


@api.route('/companies')
def companyList():
    """Retrieve JSON of all company objects unfiltered."""
    with session_scope() as session:
        companies = session.query(Company).all()
        return jsonify(companies=[
                company.serialize for company in companies])


@api.route('/manufacturers')
def manufacturerList():
    """Retrieve JSON of all manufacturer company objects."""
    with session_scope() as session:
        manufacturers = session.query(Company).filter_by(
            company_type='manufacturer').all()
        return jsonify(manufacturers=[
                manufacturer.serialize for manufacturer in manufacturers])


@api.route('/publishers')
def publisherList():
    """Retrieve JSON of all publisher company objects."""
    with session_scope() as session:
        publishers = session.query(Company).filter_by(
            company_type='publisher').all()
        return jsonify(publishers=[
            publisher.serialize for publisher in publishers])


@api.route('/systems')
def systemList():
    """Retrieve JSON of all system objects."""
    with session_scope() as session:
        systems = session.query(System).all()
        return jsonify(systems=[system.serialize for system in systems])


@api.route('/images')
def imageList():
    """Retrieve JSON of all image objects."""
    with session_scope() as session:
        images = session.query(Image).all()
        return jsonify(images=[image.serialize for image in images])