FROM debian:bookworm-slim

RUN apt-get update && DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get install -y curl jq gosu
