#!/bin/sh
# php-fpm をバックグラウンドで起動し、nginx をフォアグラウンドで走らせる。
# nginx が落ちたらコンテナも落ちるので、Docker のヘルスチェックが機能する。
set -e
envsubst '${PHP_FPM_CHILDREN}' < /usr/local/etc/php-fpm.d/zz-bench.conf.tpl > /usr/local/etc/php-fpm.d/zz-bench.conf
php-fpm -D
exec nginx -g 'daemon off;'
