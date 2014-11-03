from conf.appconfig import API_PORT
from deployer.server import app


if __name__ == '__main__':
    app.run(debug=False,
            threaded=True,
            host='0.0.0.0',
            port=API_PORT)
