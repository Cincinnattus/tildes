apt_distro: bionic
gunicorn_args: --workers 8
ini_file: production.ini
ssl_cert_path: /etc/letsencrypt/live/tildes.net/fullchain.pem
ssl_private_key_path: /etc/letsencrypt/live/tildes.net/privkey.pem
hsts_max_age: 63072000
nginx_worker_processes: auto
postgresql_version: 12
prometheus_ips: ['2607:5300:201:3100::6e77']
site_hostname: tildes.net
ipv6_address: '2607:5300:0203:2dd8::'
ipv6_gateway: '2607:5300:0203:2dff:ff:ff:ff:ff'
