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

auth = HTTPBasicAuth()
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


def getUserId(email):
    with session_scope() as session:
        try:
            user = session.query(User).filter_by(email=email).one()
            return user.id
        except:
            return None

def getUserInfo(user_id):
    with session_scope() as session:
        user = session.query(User).filter_by(id = user_id).one()
        return user


def createUser(login_session):
    with session_scope() as session:
        newUser = User(
            name=login_session['username'],
            email=login_session['email'],
            picture=login_session['picture'])
        session.add(newUser)
        session.commit()
        user = session.query(User).filter_by(email=login_session['email']).one()
        return user.id


CLIENT_ID = json.loads(open('client_secrets.json', 'r').read())['web']['client_id']


# Create anti-forgery state token
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in range(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print("Token's client ID does not match app's.")
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']
    login_session['provider'] = 'google'

    user_id = getUserId(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print("done!")
    return output


@app.route('/fbconnect', methods=['POST'])
def fbconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = request.data
    print( "access token received {0}".format(access_token))


    app_id = json.loads(open('fbclientsecrets.json', 'r').read())[
        'web']['app_id']
    app_secret = json.loads(
        open('fbclientsecrets.json', 'r').read())['web']['app_secret']
    url = 'https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=%s&client_secret=%s&fb_exchange_token=%s' % (
        app_id, app_secret, access_token)
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]


    # Use token to get user info from API
    userinfo_url = "https://graph.facebook.com/v2.8/me"
    '''
        Due to the formatting for the result from the server token exchange we have to
        split the token first on commas and select the first index which gives us the key : value
        for the server access token then we split it on colons to pull out the actual token value
        and replace the remaining quotes with nothing so that it can be used directly in the graph
        api calls
    '''
    token = result.split(',')[0].split(':')[1].replace('"', '')

    url = 'https://graph.facebook.com/v2.8/me?access_token=%s&fields=name,id,email' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    # print "url sent for API access:%s"% url
    # print "API JSON result: %s" % result
    data = json.loads(result)
    login_session['provider'] = 'facebook'
    login_session['username'] = data["name"]
    login_session['email'] = data["email"]
    login_session['facebook_id'] = data["id"]

    # The token must be stored in the login_session in order to properly logout
    login_session['access_token'] = token

    # Get user picture
    url = 'https://graph.facebook.com/v2.8/me/picture?access_token=%s&redirect=0&height=200&width=200' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    data = json.loads(result)

    login_session['picture'] = data["data"]["url"]

    # see if user exists
    user_id = getUserId(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']

    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '

    flash("Now logged in as %s" % login_session['username'])
    return output

@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session.get('access_token')
    if access_token is None:
        print('Access Token is None')
        response = make_response(json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    print('In gdisconnect access token is %s', access_token)
    print('User name is: ')
    print(login_session['username'])
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print( 'result is ')
    print( result)
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        response = make_response(json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response

@app.route('/fbdisconnect')
def fbdisconnect():
    facebook_id = login_session['facebook_id']
    url = 'https://graph.facebook.com/{0}/permissions'.format(facebook_id)
    h = httplib2.Http()
    result = h.request(url, 'DELETE')[1]
    del login_session['username']
    del login_session['email']
    del login_session['picture']
    del login_session['user_id']
    del login_session['facebook_id']
    return "You have been logged out"


@app.route('/disconnect')
def disconnect():
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
        if login_session['provider'] == 'facebook':
            fbdisconnect()
        del login_session['provider']
        flash("You have successfully been logged out.")
        return redirect(url_for('default'))
    else:
        flash("You were not logged in")
        return redirect(url_for('default'))


@app.route('/')
def default():
    with session_scope() as session:
        top_games = session.query(Game,Image).filter(Game.image_id == Image.id).order_by(Game.average_rating.desc()).limit(3)
        games = session.query(Game,Image).filter(Game.image_id == Image.id).order_by(Game.created_date.desc()).limit(10)
        systems = session.query(System,Image).filter(System.image_id == Image.id).all()
        return render_template('default.html', top_games=top_games, games=games, systems=systems)


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
    app.secret_key = secret_key
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
