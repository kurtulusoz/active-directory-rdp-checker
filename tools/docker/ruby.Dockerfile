FROM ruby:3.3-alpine

# Build tools for native extensions
RUN apk add --no-cache build-base

WORKDIR /app

# necessary gems
RUN gem install sinatra rackup puma -N

# Copy the files from the build context.
COPY ./script/sinatra_app.rb /app/app.rb

EXPOSE 8080
# Start with Ruby instead of Rackup (the most reliable way for classic Sinatra).
CMD ["ruby", "app.rb"]
