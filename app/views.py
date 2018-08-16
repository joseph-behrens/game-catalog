from flask import (Flask, render_template, request, redirect,
                   jsonify, url_for, flash, make_response)
from flask import session as login_session
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from models import (Base, Image, Rating, Company, Manufacturer, Publisher,
                    Developer, System, User, Role, UserRole, Game,
                    GamePlatform)
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
import requests
import random
import string


app = Flask(__name__)


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


@app.route('/')
def default():
    with session_scope() as session:
        developer = session.query(Company).filter_by(id=1).first()
        return render_template('default.html', developer=developer)


@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/admin')
def admin():
    return render_template('admin.html')


@app.route('/game/<int:game_id>')
def game(game_id):
    return render_template('game.html', game_id=game_id)


@app.route('/game/new', methods=['GET','POST'])
def newGame():
    with session_scope() as session:
        images = session.query(Image).all()
        systems = session.query(System).all()
        manufacturers = session.query(Manufacturer).all()
        publishers = session.query(Publisher).all()
        print(images[0].url)
        if request.method == 'GET':
            return render_template('new-game.html',
                                    images=images,
                                    systems=systems,
                                    manufacturers=manufacturers,
                                    publishers=publishers)
        if request.method == 'POST':
            game_title =  request.form["title"]
            game_description =  request.form["description"]
            game_release_year = request.form["year_released"]
            game_rating = request.form["initial_rating"]
            result = "{0}\n{1}\n{2}\n{3}".format(game_title, game_description, game_release_year, game_rating)
            return result



@app.route('/game/<int:game_id>/edit')
def editGame(game_id):
    return render_template('edit-game.html', game_id=game_id)


@app.route('/game/<int:game_id>/delete')
def deleteGame(game_id):
    return render_template('delete-game.html', game_id=game_id)


@app.route('/api/v1/games')
def gamesList():
    with session_scope() as session:
        games = session.query(Game).all()
        return jsonify(games=[game.serialize for game in games])


@app.route('/api/v1/manufacturers')
def manufacturerList():
    with session_scope() as session:
        manufacturers = session.query(Company).filter_by(
            company_type='Manufacturer').all()
        return jsonify(manufacturers=[
                manufacturer.serialize for manufacturer in manufacturers])


@app.route('/api/v1/publishers')
def publisherList():
    with session_scope() as session:
        publishers = session.query(Company).filter_by(
            company_type='Publisher').all()
        return jsonify(publishers=[
            publisher.serialize for publisher in publishers])


@app.route('/api/v1/developers')
def developerList():
    with session_scope() as session:
        developers = session.query(Company).filter_by(
            company_type='Developer').all()
        return jsonify(developers=[
            developer.serialize for developer in developers])


@app.route('/api/v1/systems')
def systemList():
    with session_scope() as session:
        systems = session.query(Company).filter_by(company_type='System').all()
        return jsonify(systems=[system.serialize for system in systems])


if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
