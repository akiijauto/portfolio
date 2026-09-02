# frozen_string_literal: true

# 3言語共通仕様のスコアリングAPI（Ruby実装・HTTP層）。
# 計算ロジックは core.rb に置いてある。

require 'sinatra/base'
require 'json'
require_relative 'core'

class ScoreApp < Sinatra::Base
  set :environment, :production
  set :logging, false
  set :show_exceptions, false

  @@processed = 0

  post '/api/v1/score' do
    content_type :json
    begin
      req = JSON.parse(request.body.read)
    rescue JSON::ParserError
      halt 400, JSON.generate(error: 'invalid_json')
    end

    begin
      body = Score.compute(req)
    rescue Score::ValidationError, NoMethodError
      halt 400, JSON.generate(error: 'validation_failed')
    end

    @@processed += 1
    JSON.generate(body)
  end

  get '/healthz' do
    content_type :json
    JSON.generate(status: 'ok', lang: 'ruby')
  end

  get '/metrics' do
    content_type :json
    JSON.generate(lang: 'ruby', processed: @@processed, pid: Process.pid)
  end
end
