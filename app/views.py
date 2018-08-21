from flask import (Flask, render_template, request, redirect,
                   jsonify, url_for, flash, make_response)
from flask import session as login_session
from sqlalchemy import create_engine, asc, desc
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
import sys


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
        top_games = session.query(Game,Image).filter(Game.image_id == Image.id).order_by(Game.average_rating.desc()).limit(3)
        games = session.query(Game,Image).filter(Game.image_id == Image.id).order_by(Game.created_date.desc()).limit(10)
        systems = session.query(System,Image).filter(System.image_id == Image.id).all()
        return render_template('default.html', top_games=top_games, games=games, systems=systems)


@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/admin')
def admin():
    return render_template('admin.html')


#region Game Methods
@app.route('/game')
def allGames():
    with session_scope() as session:
        games = session.query(Game,Image,System,Company).filter(Game.image_id == Image.id).filter(Game.system_id == System.id).filter(Game.publisher_id == Company.id).all()
        return render_template('all-games.html', games=games)
        

@app.route('/game/<int:game_id>')
def game(game_id):
    with session_scope() as session:
        game = session.query(Game,Image,System,Company).filter(Game.image_id == Image.id).filter(Game.system_id == System.id).filter(Game.publisher_id == Company.id).filter_by(id=game_id).first()
        return render_template('game.html', game=game)


@app.route('/game/new', methods=['GET','POST'])
def newGame():
    with session_scope() as session:
        images = session.query(Image).order_by(Image.alt_text).all()
        systems = session.query(System).order_by(System.name).all()
        manufacturers = session.query(Manufacturer).order_by(Manufacturer.name).all()
        publishers = session.query(Publisher).order_by(Publisher.name).all()
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
            game_image = session.query(Image).filter_by(id=request.form["image"]).first()
            game_publisher = session.query(Company).filter_by(id=request.form["publisher"]).first()
            game_system = session.query(System).filter_by(id=request.form["system"]).first()

            game = Game(
                   title=game_title,
                   description=game_description,
                   year_released=game_release_year,
                   average_rating=game_rating,
                   image_id=game_image.id,
                   system_id=game_system.id,
                   owner_id=1, # TODO: Change once logins are setup
                   publisher_id=game_publisher.id
                   )

            session.add(game)
            session.commit()
            return redirect(url_for('default'))


@app.route('/game/<int:game_id>/edit', methods=['GET','POST'])
def editGame(game_id):
    with session_scope() as session:
        game = session.query(Game).filter_by(id=game_id).first()
        if request.method == 'GET':
            images = session.query(Image).order_by(Image.alt_text).all()
            systems = session.query(System).order_by(System.name).all()
            manufacturers = session.query(Manufacturer).order_by(Manufacturer.name).all()
            publishers = session.query(Publisher).order_by(Publisher.name).all()
            return render_template('edit-game.html',
                                    game=game,
                                    images=images,
                                    systems=systems,
                                    manufacturers=manufacturers,
                                    publishers=publishers)
                                    
        if request.method == 'POST':
            game.title =  request.form["title"]
            game.description =  request.form["description"]
            game.year_released = request.form["year_released"]
            game.average_rating = request.form["initial_rating"]

            game_image = session.query(Image).filter_by(id=request.form["image"]).first()
            game_publisher = session.query(Company).filter_by(id=request.form["publisher"]).first()
            game_system = session.query(System).filter_by(id=request.form["system"]).first()

            game.image_id=game_image.id
            game.system_id=game_system.id
            game.owner_id=1 # TODO: Change once logins are setup
            game.publisher_id=game_publisher.id

            session.add(game)
            session.commit()
            return redirect(url_for('game', game_id=game.id))


@app.route('/game/<int:game_id>/delete', methods=['GET','POST'])
def deleteGame(game_id):
    with session_scope() as session:
        game = session.query(Game).filter_by(id=game_id).first()
        if request.method == 'GET':
            return render_template('delete-game.html', game=game)
        if request.method == 'POST':
            session.delete(game)
            session.commit()
            return redirect(url_for('default'))
#endregion


#region Image Methods
@app.route('/image/new', methods=['GET','POST'])
def newImage():
    with session_scope() as session:
        if request.method == 'GET':
            return render_template('new-image.html')
        if request.method == 'POST':
            image = Image(
                    url=request.form["url"],
                    alt_text=request.form["alt_text"]
                    )
            session.add(image)
            session.commit()
            return redirect(url_for('allImages'))


@app.route('/image')
def allImages():
    with session_scope() as session:
        images = session.query(Image).order_by(Image.alt_text).all()
        return render_template('all-images.html', images=images)


@app.route('/image/<int:image_id>/edit', methods=['GET','POST'])
def editImage(image_id):
    with session_scope() as session:
        image = session.query(Image).filter_by(id=image_id).first()
        if request.method == 'GET':
            return render_template('edit-image.html', image=image)
        if request.method == 'POST':
            image.alt_text = request.form['alt_text']
            image.url = request.form['url']
            session.add(image)
            session.commit()
            return redirect(url_for('allImages'))


@app.route('/image/<int:image_id>/delete', methods=['GET','POST'])
def deleteImage(image_id):
    with session_scope() as session:
        image = session.query(Image).filter_by(id=image_id).first()
        if request.method == 'GET':
            return render_template('delete-image.html', image=image)
        if request.method == 'POST':
            session.delete(image)
            session.commit()
            return redirect(url_for('allImages'))
#endregion


#region Publisher Methods
@app.route('/publisher/new', methods=['GET','POST'])
def newPublisher():
    with session_scope() as session:
        images = session.query(Image).order_by(Image.alt_text).all()
        if request.method == 'GET':
            return render_template('new-publisher.html', images=images)
        if request.method == 'POST':
            publisher = Publisher(
                        name=request.form["publisher_name"],
                        country=request.form["publisher_country"],
                        image_id=request.form["publisher_image"]
                        )
            session.add(publisher)
            session.commit()
            return redirect(url_for('allPublishers'))


@app.route('/publisher')
def allPublishers():
    with session_scope() as session:
        publishers = session.query(Publisher,Image).filter(Publisher.image_id == Image.id).order_by(Publisher.name).all()
        return render_template('all-publishers.html', publishers=publishers)


@app.route('/publisher/<int:publisher_id>/edit', methods=['GET','POST'])
def editPublisher(publisher_id):
    with session_scope() as session:
        publisher = session.query(Publisher).filter_by(id=publisher_id).first()
        images = session.query(Image).order_by(Image.alt_text).all()
        if request.method == 'GET':
            return render_template('edit-publisher.html', publisher=publisher, images=images)
        if request.method == 'POST':
            publisher.name = request.form['publisher_name']
            publisher.country = request.form['publisher_country']
            publisher.image_id = request.form['publisher_image']
            session.add(publisher)
            session.commit()
            return redirect(url_for('allPublishers'))


@app.route('/publisher/<int:publisher_id>/delete', methods=['GET','POST'])
def deletePublisher(publisher_id):
    with session_scope() as session:
        publisher = session.query(Publisher).filter_by(id=publisher_id).first()
        if request.method == 'GET':
            return render_template('delete-publisher.html', publisher=publisher)
        if request.method == 'POST':
            session.delete(publisher)
            session.commit()
            return redirect(url_for('allPublishers'))
#endregion


#region System Methods
@app.route('/system/<int:system_id>')
def gamesBySystem(system_id):
    with session_scope() as session:
        system = session.query(System,Image).filter(System.image_id == Image.id).filter_by(id=system_id).first()
        games = session.query(Game,Image).filter(Game.image_id == Image.id).filter(Game.system_id == system_id).all()
        return render_template('system.html', system=system, games=games)


@app.route('/system/new', methods=['GET','POST'])
def newSystem():
    with session_scope() as session:
        images = session.query(Image).order_by(Image.alt_text).all()
        manufacturers = session.query(Manufacturer).order_by(Manufacturer.name).all()
        if request.method == 'GET':
            return render_template('new-system.html', images=images, manufacturers=manufacturers)
        if request.method == 'POST':
            system = System(
                        name=request.form["system_name"],
                        image_id=request.form["system_image"],
                        year_released=request.form["system_release_year"],
                        description=request.form["system_description"]
                        )
            session.add(system)
            session.commit()
            return redirect(url_for('allSystems'))


@app.route('/system')
def allSystems():
    with session_scope() as session:
        systems = session.query(System,Image).filter(System.image_id == Image.id).order_by(System.name).all()
        return render_template('all-systems.html', systems=systems)


@app.route('/system/<int:system_id>/edit', methods=['GET','POST'])
def editSystem(system_id):
    with session_scope() as session:
        system = session.query(System).filter_by(id=system_id).first()
        if request.method == 'GET':
            manufacturers = session.query(Manufacturer).order_by(Manufacturer.name).all()
            images = session.query(Image).order_by(Image.alt_text).all()
            return render_template('edit-system.html', system=system, manufacturers=manufacturers, images=images)
        if request.method == 'POST':
            system.name = request.form['system_name']
            system.manufacturer_id = request.form['manufacturer']
            system.description = request.form['system_description']
            system.year_released = request.form['system_release_year']
            system.image_id = request.form['system_image']
            session.add(system)
            session.commit()
            return redirect(url_for('allSystems'))


@app.route('/system/<int:system_id>/delete', methods=['GET','POST'])
def deleteSystem(system_id):
    with session_scope() as session:
        system = session.query(System).filter_by(id=system_id).first()
        if request.method == 'GET':
            return render_template('delete-system.html', system=system)
        if request.method == 'POST':
            session.delete(system)
            session.commit()
            return redirect(url_for('allSystems'))
#endregion


#region Manufacturer Methods
@app.route('/manufacturer/new', methods=['GET','POST'])
def newManufacturer():
    with session_scope() as session:
        images = session.query(Image).order_by(Image.alt_text).all()
        if request.method == 'GET':
            return render_template('new-manufacturer.html', images=images)
        if request.method == 'POST':
            manufacturer = Manufacturer(
                        name=request.form["manufacturer_name"],
                        country=request.form["manufacturer_country"],
                        image_id=request.form["manufacturer_image"],
                        year_founded=request.form["year_founded"]
                        )
            session.add(manufacturer)
            session.commit()
            return redirect(url_for('allManufacturers'))


@app.route('/manufacturer')
def allManufacturers():
    with session_scope() as session:
        manufacturers = session.query(Manufacturer,Image).filter(Manufacturer.image_id == Image.id).all()
        return render_template('all-manufacturers.html', manufacturers=manufacturers)


@app.route('/manufacturer/<int:manufacturer_id>/edit', methods=['GET','POST'])
def editManufacturer(manufacturer_id):
    with session_scope() as session:
        manufacturer = session.query(Manufacturer).filter_by(id=manufacturer_id).first()
        if request.method == 'GET':
            images = session.query(Image).order_by(Image.alt_text).all()
            return render_template('edit-manufacturer.html', manufacturer=manufacturer, images=images)
        if request.method == 'POST':
            manufacturer.name = request.form['manufacturer_name']
            manufacturer.country = request.form['manufacturer_country']
            manufacturer.year_founded = request.form['year_founded']
            manufacturer.image_id = request.form['manufacturer_image']
            session.add(manufacturer)
            session.commit()
            return redirect(url_for('allManufacturers'))


@app.route('/manufacturer/<int:manufacturer_id>/delete', methods=['GET','POST'])
def deleteManufacturer(manufacturer_id):
    with session_scope() as session:
        manufacturer = session.query(Manufacturer).filter_by(id=manufacturer_id).first()
        if request.method == 'GET':
            return render_template('delete-manufacturer.html', manufacturer=manufacturer)
        if request.method == 'POST':
            session.delete(manufacturer)
            session.commit()
            return redirect(url_for('allManufacturers'))
#endregion


#region API Calls
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
        systems = session.query(System).all()
        return jsonify(systems=[system.serialize for system in systems])
#endregion


if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
