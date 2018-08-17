FROM nginx:1.13.3

RUN rm /etc/nginx/nginx.conf
COPY nginx.conf /etc/nginx/

RUN rm /etc/nginx/conf.d/default.conf
COPY project.conf /etc/nginx/conf.d/

COPY joebehrens.crt /etc/ssl/joebehrens.crt
COPY joebehrens.rsa /etc/ssl/joebehrens.rsa

COPY ./static ./static