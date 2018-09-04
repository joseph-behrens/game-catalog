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
from flask_httpauth import HTTPBasicAuth
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
from models import secret_key
import google.oauth2.credentials
import google_auth_oauthlib.flow
from os import environ
from oauth2client.contrib.flask_util import UserOAuth2
from googleapiclient.discovery import build
from functools import wraps


# Import API package
from api.api import api


# Setup application to use Google OAuth
auth = HTTPBasicAuth()
app = Flask(__name__)
app.register_blueprint(api)
app.secret_key = secret_key
app.config.update(dict(PREFERRED_URL_SCHEME='https'))
oauth2 = UserOAuth2()
CLIENT_ID = json.loads(open(
                'client_secrets.json', 'r').read())['web']['client_id']
CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = [
    'https://www.googleapis.com/auth/plus.me',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile']
API_SERVICE_NAME = 'drive'
API_VERSION = 'v2'
environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


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


def getUserId(email):
    """Retrievie the user id from the User database using email."""
    with session_scope() as session:
        try:
            user = session.query(User).filter_by(email=email).one()
            return user.id
        except Exception:
            return None


def getUserInfo(user_id):
    """Get a user from the database by user id number."""
    with session_scope() as session:
        user = session.query(User).filter_by(id=user_id).one()
        return user


def createUser(login_session):
    """Create a new user in the database from the info in Google."""
    with session_scope() as session:
        newUser = User(
            name=login_session['username'],
            email=login_session['email'],
            picture=login_session['picture'])
        session.add(newUser)
        session.commit()
        user = session.query(User).filter_by(
            email=login_session['email']).one()
        return user.id


def login_required(f):
    """Decorate to require user session to access route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' in login_session:
            return f(*args, **kwargs)
        else:
            flash("Access denied. You must be logged in to access that.")
            return redirect(url_for('default'))
    return decorated_function


@app.route('/authorize')
def authorize():
    """
    Set the state and authorization.

    Use to pass on to the oath2callback method to get user
    info from the Google api.
    Redirects to the Google authorization page and then
    builds the user information once login is successful.

    Create flow instance to manage the
    OAuth 2.0 Authorization Grant Flow steps.
    """
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES)

    flow.redirect_uri = url_for('oauth2callback', _external=True)

    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission.
        # Recommended for web server apps.
        access_type='offline',
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes='true')

    # Store the state so the callback can verify the auth server response.
    login_session['state'] = state

    return redirect(authorization_url)


@app.route('/oauth2callback')
def oauth2callback():
    """
    Build the authentication session with Google OAuth2 API.

    Create a user in the local apps database if there isn't already
    a matching user.

    Specify the state when creating the flow in the callback so that it can
    be verified in the authorization server response.
    """
    try:
        state = login_session['state']
        if request.args.get('state') != login_session['state']:
            response = make_response(
                json.dumps('Invalid state parameter.'), 401)
            response.headers['Content-Type'] = 'application/json'
            return response
    except Exception:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = url_for('oauth2callback', _external=True)

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = request.url
    access_token = flow.fetch_token(
        authorization_response=authorization_response)

    # Store credentials in the session.
    credentials = flow.credentials
    login_session['credentials'] = credentials_to_dict(credentials)
    login_session['access_token'] = access_token
    url = 'https://www.googleapis.com/oauth2/v1/userinfo?alt=json&access_token={0}'.format(access_token['access_token'])  # noqa: E501
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    login_session['email'] = result['email']
    login_session['username'] = result['name']
    login_session['picture'] = result['picture']
    login_session['provider'] = 'google'

    # If this is the rist login for the user create
    # a new user in the database.
    user_id = getUserId(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id
    return redirect(request.referrer or '/')


@app.route('/disconnect')
def disconnect():
    """Initialize via logout, deletes all user session data."""
    if 'username' not in login_session:
        flash('No login session available to sign out.')
        return redirect(url_for('default'))

    credentials = google.oauth2.credentials.Credentials(
                    **login_session['credentials'])

    revoke = requests.post('https://accounts.google.com/o/oauth2/revoke',
                           params={'token': credentials.token},
                           headers={'content-type': 'application/x-www-form-urlencoded'})  # noqa: E501

    status_code = getattr(revoke, 'status_code')
    if status_code == 200:
        if 'credentials' in login_session:
            del login_session['credentials']
            del login_session['access_token']
            del login_session['email']
            del login_session['username']
            del login_session['picture']
            del login_session['provider']
        login_session.modified = True
        return redirect(url_for('default'))
    else:
        flash('An error occurred revoking credentials')
        return redirect(url_for('default'))


def credentials_to_dict(credentials):
    """Extend the authorization method used to create credentials object."""
    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes}


@app.route('/')
def default():
    """Set up default page."""
    with session_scope() as session:
        top_games = session.query(Game, Image).filter(
            Game.image_id == Image.id).order_by(
                Game.average_rating.desc()).limit(3)
        games = session.query(Game, Image).filter(
            Game.image_id == Image.id).order_by(
                Game.created_date.desc()).limit(10)
        systems = session.query(System, Image).filter(
            System.image_id == Image.id).all()
        return render_template('default.html',
                               top_games=top_games,
                               games=games,
                               systems=systems)


@app.route('/admin')
@login_required
def admin():
    """For enhancement of setting up different user roles."""
    return render_template('admin.html')


# region Game Methods
@app.route('/game')
def allGames():
    """Display a list of all games in the system."""
    with session_scope() as session:
        games = session.query(Game, Image, System, Company).filter(
            Game.image_id == Image.id).filter(
                Game.system_id == System.id).filter(
                    Game.publisher_id == Company.id).all()
        return render_template('all-games.html', games=games)


@app.route('/game/<int:game_id>')
def game(game_id):
    """Details of a specific game."""
    with session_scope() as session:
        game = session.query(Game, Image, System, Company, User).filter(
            Game.image_id == Image.id).filter(
                Game.system_id == System.id).filter(
                    Game.publisher_id == Company.id).filter(
                        Game.owner_id == User.id).filter_by(
                            id=game_id).first()
        return render_template('game.html', game=game)


@app.route('/game/new', methods=['GET', 'POST'])
@login_required
def newGame():
    """Add game article creation form."""
    with session_scope() as session:
        images = session.query(Image).order_by(Image.alt_text).all()
        systems = session.query(System).order_by(System.name).all()
        manufacturers = session.query(Manufacturer).order_by(
            Manufacturer.name).all()
        publishers = session.query(Publisher).order_by(
            Publisher.name).all()
        print(images[0].url)
        if request.method == 'GET':
            return render_template('new-game.html',
                                   images=images,
                                   systems=systems,
                                   manufacturers=manufacturers,
                                   publishers=publishers)
        if request.method == 'POST':
            game_title = request.form["title"]
            game_description = request.form["description"]
            game_release_year = request.form["year_released"]
            game_rating = request.form["initial_rating"]
            game_image = session.query(Image).filter_by(
                id=request.form["image"]).first()
            game_publisher = session.query(Company).filter_by(
                id=request.form["publisher"]).first()
            game_system = session.query(System).filter_by(
                id=request.form["system"]).first()

            game = Game(
                   title=game_title,
                   description=game_description,
                   year_released=game_release_year,
                   average_rating=game_rating,
                   image_id=game_image.id,
                   system_id=game_system.id,
                   owner_id=login_session['user_id'],
                   publisher_id=game_publisher.id
                   )

            session.add(game)
            session.commit()
            return redirect(url_for('default'))


@app.route('/game/<int:game_id>/edit', methods=['GET', 'POST'])
@login_required
def editGame(game_id):
    """Edit a game if you are the owner and logged in."""
    with session_scope() as session:
        game = session.query(Game).filter_by(id=game_id).first()
        # Authorize the authenticated user
        if login_session['user_id'] != game.owner_id:
            flash('Only the creator is allowed to edit this item.')
            return redirect('/game/' + str(game_id))
        if request.method == 'GET':
            images = session.query(Image).order_by(Image.alt_text).all()
            systems = session.query(System).order_by(System.name).all()
            manufacturers = session.query(Manufacturer).order_by(
                Manufacturer.name).all()
            publishers = session.query(Publisher).order_by(
                Publisher.name).all()
            return render_template('edit-game.html',
                                   game=game,
                                   images=images,
                                   systems=systems,
                                   manufacturers=manufacturers,
                                   publishers=publishers)

        if request.method == 'POST':
            game.title = request.form["title"]
            game.description = request.form["description"]
            game.year_released = request.form["year_released"]
            game.average_rating = request.form["initial_rating"]

            game_image = session.query(Image).filter_by(
                id=request.form["image"]).first()
            game_publisher = session.query(Company).filter_by(
                id=request.form["publisher"]).first()
            game_system = session.query(System).filter_by(
                id=request.form["system"]).first()

            game.image_id = game_image.id
            game.system_id = game_system.id
            game.editor_id = login_session['user_id']
            game.publisher_id = game_publisher.id

            session.add(game)
            session.commit()
            return redirect(url_for('game', game_id=game.id))


@app.route('/game/<int:game_id>/delete', methods=['GET', 'POST'])
@login_required
def deleteGame(game_id):
    """Delete a game if you are the owner and logged in."""
    with session_scope() as session:
        game = session.query(Game).filter_by(id=game_id).first()
        # Authorize the authenticated user
        if login_session['user_id'] != game.owner_id:
            flash('Only the creator is allowed to edit this item.')
            return redirect('/game/' + str(game_id))
        if request.method == 'GET':
            return render_template('delete-game.html', game=game)
        if request.method == 'POST':
            session.delete(game)
            session.commit()
            return redirect(url_for('default'))
# endregion


# region Image Methods
@app.route('/image/new', methods=['GET', 'POST'])
@login_required
def newImage():
    """Create a new image entry in db."""
    with session_scope() as session:
        if request.method == 'GET':
            return render_template('new-image.html')
        if request.method == 'POST':
            image = Image(
                    url=request.form["url"],
                    alt_text=request.form["alt_text"],
                    owner_id=login_session['user_id']
                    )
            session.add(image)
            session.commit()
            return redirect(url_for('allImages'))


@app.route('/image')
def allImages():
    """View all images in the system."""
    with session_scope() as session:
        images = session.query(Image).order_by(Image.alt_text).all()
        return render_template('all-images.html', images=images)


@app.route('/image/<int:image_id>/edit', methods=['GET', 'POST'])
@login_required
def editImage(image_id):
    """Edit an image once authenticated."""
    with session_scope() as session:
        image = session.query(Image).filter_by(id=image_id).first()
        # Authorize the authenticated user
        if login_session['user_id'] != image.owner_id:
            flash('Only the creator is allowed to edit this item.')
            return redirect(url_for('allImages'))
        if request.method == 'GET':
            return render_template('edit-image.html', image=image)
        if request.method == 'POST':
            image.alt_text = request.form['alt_text']
            image.url = request.form['url']
            session.add(image)
            session.commit()
            return redirect(url_for('allImages'))


@app.route('/image/<int:image_id>/delete', methods=['GET', 'POST'])
@login_required
def deleteImage(image_id):
    """Delete an image once authenticated."""
    with session_scope() as session:
        image = session.query(Image).filter_by(id=image_id).first()
        # Authorize the authenticated user
        if login_session['user_id'] != image.owner_id:
            flash('Only the creator is allowed to edit this item.')
            return redirect(url_for('allImages'))
        if request.method == 'GET':
            return render_template('delete-image.html', image=image)
        if request.method == 'POST':
            session.delete(image)
            session.commit()
            return redirect(url_for('allImages'))
# endregion


# region Publisher Methods
@app.route('/publisher/new', methods=['GET', 'POST'])
@login_required
def newPublisher():
    """Create a publisher once authenticated."""
    with session_scope() as session:
        images = session.query(Image).order_by(Image.alt_text).all()
        if request.method == 'GET':
            return render_template('new-publisher.html', images=images)
        if request.method == 'POST':
            publisher = Publisher(
                        name=request.form["publisher_name"],
                        country=request.form["country"],
                        image_id=request.form["publisher_image"],
                        owner_id=login_session['user_id']
                        )
            session.add(publisher)
            session.commit()
            return redirect(url_for('allPublishers'))


@app.route('/publisher')
def allPublishers():
    """View all publishers."""
    with session_scope() as session:
        publishers = session.query(Publisher, Image).filter(
            Publisher.image_id == Image.id).order_by(Publisher.name).all()
        return render_template('all-publishers.html',
                               publishers=publishers)


@app.route('/publisher/<int:publisher_id>/edit', methods=['GET', 'POST'])
@login_required
def editPublisher(publisher_id):
    """Edit an publisher once authenticated."""
    with session_scope() as session:
        publisher = session.query(Publisher).filter_by(id=publisher_id).first()
        images = session.query(Image).order_by(Image.alt_text).all()
        # Authorize the authenticated user
        if login_session['user_id'] != publisher.owner_id:
            flash('Only the creator is allowed to edit this item.')
            return redirect(url_for('allPublishers'))
        if request.method == 'GET':
            return render_template('edit-publisher.html',
                                   publisher=publisher,
                                   images=images)
        if request.method == 'POST':
            publisher.name = request.form['publisher_name']
            publisher.country = request.form['country']
            publisher.image_id = request.form['publisher_image']
            session.add(publisher)
            session.commit()
            return redirect(url_for('allPublishers'))


@app.route('/publisher/<int:publisher_id>/delete', methods=['GET', 'POST'])
@login_required
def deletePublisher(publisher_id):
    """Delete a publisher once authenticated."""
    with session_scope() as session:
        publisher = session.query(Publisher).filter_by(id=publisher_id).first()
        # Authorize the authenticated user
        if login_session['user_id'] != publisher.owner_id:
            flash('Only the creator is allowed to edit this item.')
            return redirect(url_for('allPublishers'))
        if request.method == 'GET':
            return render_template('delete-publisher.html',
                                   publisher=publisher)
        if request.method == 'POST':
            session.delete(publisher)
            session.commit()
            return redirect(url_for('allPublishers'))
# endregion


# region System Methods
@app.route('/system/<int:system_id>')
def gamesBySystem(system_id):
    """View games filtered by game system they run on."""
    with session_scope() as session:
        system = session.query(System, Image).filter(
            System.image_id == Image.id).filter_by(
                id=system_id).first()
        games = session.query(Game, Image).filter(
            Game.image_id == Image.id).filter(
                Game.system_id == system_id).all()
        return render_template('system.html', system=system, games=games)


@app.route('/system/new', methods=['GET', 'POST'])
@login_required
def newSystem():
    """Create a new system entry."""
    with session_scope() as session:
        images = session.query(Image).order_by(Image.alt_text).all()
        manufacturers = session.query(Manufacturer).order_by(
            Manufacturer.name).all()
        if request.method == 'GET':
            return render_template('new-system.html',
                                   images=images,
                                   manufacturers=manufacturers)
        if request.method == 'POST':
            system = System(
                        name=request.form["system_name"],
                        image_id=request.form["system_image"],
                        year_released=request.form["system_release_year"],
                        description=request.form["system_description"],
                        manufacturer_id=request.form["manufacturer"],
                        owner_id=login_session['user_id']
                        )
            session.add(system)
            session.commit()
            return redirect(url_for('allSystems'))


@app.route('/system')
def allSystems():
    """View all systems."""
    with session_scope() as session:
        systems = session.query(System, Image).filter(
            System.image_id == Image.id).order_by(
                System.name).all()
        return render_template('all-systems.html',
                               systems=systems)


@app.route('/system/<int:system_id>/edit', methods=['GET', 'POST'])
@login_required
def editSystem(system_id):
    """Edit an existing system entry."""
    with session_scope() as session:
        system = session.query(System).filter_by(id=system_id).first()
        # Authorize the authenticated user
        if login_session['user_id'] != system.owner_id:
            flash('Only the creator is allowed to edit this item.')
            return redirect(url_for('allSystems'))
        if request.method == 'GET':
            manufacturers = session.query(Manufacturer).order_by(
                Manufacturer.name).all()
            images = session.query(Image).order_by(Image.alt_text).all()
            return render_template('edit-system.html',
                                   system=system,
                                   manufacturers=manufacturers,
                                   images=images)
        if request.method == 'POST':
            system.name = request.form['system_name']
            system.manufacturer_id = request.form['manufacturer']
            system.description = request.form['system_description']
            system.year_released = request.form['system_release_year']
            system.image_id = request.form['system_image']
            session.add(system)
            session.commit()
            return redirect(url_for('allSystems'))


@app.route('/system/<int:system_id>/delete', methods=['GET', 'POST'])
@login_required
def deleteSystem(system_id):
    """Delete an existing system."""
    with session_scope() as session:
        system = session.query(System).filter_by(id=system_id).first()
        # Authorize the authenticated user
        if login_session['user_id'] != system.owner_id:
            flash('Only the creator is allowed to edit this item.')
            return redirect(url_for('allSystems'))
        if request.method == 'GET':
            return render_template('delete-system.html', system=system)
        if request.method == 'POST':
            session.delete(system)
            session.commit()
            return redirect(url_for('allSystems'))
# endregion


# region Manufacturer Methods
@app.route('/manufacturer/new', methods=['GET', 'POST'])
@login_required
def newManufacturer():
    """Create a new manufacturer."""
    with session_scope() as session:
        images = session.query(Image).order_by(Image.alt_text).all()
        if request.method == 'GET':
            return render_template('new-manufacturer.html', images=images)
        if request.method == 'POST':
            manufacturer = Manufacturer(
                        name=request.form["manufacturer_name"],
                        country=request.form["country"],
                        image_id=request.form["manufacturer_image"],
                        year_founded=request.form["year_founded"],
                        owner_id=login_session['user_id']
                        )
            session.add(manufacturer)
            session.commit()
            return redirect(url_for('allManufacturers'))


@app.route('/manufacturer')
def allManufacturers():
    """View all manufacturers."""
    with session_scope() as session:
        manufacturers = session.query(Manufacturer, Image).filter(
            Manufacturer.image_id == Image.id).all()
        return render_template('all-manufacturers.html',
                               manufacturers=manufacturers)


@app.route('/manufacturer/<int:manufacturer_id>/edit', methods=['GET', 'POST'])
@login_required
def editManufacturer(manufacturer_id):
    """Edit an existing manufacturer."""
    with session_scope() as session:
        manufacturer = session.query(Manufacturer).filter_by(
            id=manufacturer_id).first()
        # Authorize the authenticated user
        if login_session['user_id'] != manufacturer.owner_id:
            flash('Only the creator is allowed to edit this item.')
            return redirect(url_for('allManufacturers'))
        if request.method == 'GET':
            images = session.query(Image).order_by(Image.alt_text).all()
            return render_template('edit-manufacturer.html',
                                   manufacturer=manufacturer,
                                   images=images)
        if request.method == 'POST':
            manufacturer.name = request.form['manufacturer_name']
            manufacturer.country = request.form['country']
            manufacturer.year_founded = request.form['year_founded']
            manufacturer.image_id = request.form['manufacturer_image']
            session.add(manufacturer)
            session.commit()
            return redirect(url_for('allManufacturers'))


@app.route('/manufacturer/<int:manufacturer_id>/delete',
           methods=['GET', 'POST'])
@login_required
def deleteManufacturer(manufacturer_id):
    """Delete and existing manufacturer."""
    with session_scope() as session:
        manufacturer = session.query(Manufacturer).filter_by(
            id=manufacturer_id).first()
        # Authorize the authenticated user
        if login_session['user_id'] != manufacturer.owner_id:
            flash('Only the creator is allowed to edit this item.')
            return redirect(url_for('allManufacturers'))
        if request.method == 'GET':
            return render_template('delete-manufacturer.html',
                                   manufacturer=manufacturer)
        if request.method == 'POST':
            session.delete(manufacturer)
            session.commit()
            return redirect(url_for('allManufacturers'))
# endregion


@app.route('/api-info')
def apiInfo():
    """Give instructions on using the api calls."""
    return render_template('api-info.html')


if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
