# frozen_string_literal: true
require 'sinatra'
require 'csv'
require 'time'

set :bind, '0.0.0.0'
set :port, 8080

CSV_DIR  = '/app/output'
FIXED    = File.join(CSV_DIR, 'rdp_check.csv')
LOG_FILE = '/tmp/csv_web.log'   # If /app/output is read-only, we write to /tmp.

helpers do
  def files_sorted
    list = Dir.glob(File.join(CSV_DIR, 'rdp_check_*.csv')).sort
    # Add the fixed file to the list if it exists.
    File.exist?(FIXED) ? (list + [FIXED]) : list
  end

  def latest_csv
    # Priority is on the fixed file.
    return FIXED if File.exist?(FIXED)
    list = files_sorted
    list.empty? ? nil : list.last
  end

  def log_line(msg)
    ts = Time.now.utc.iso8601
    line = "[#{ts}] #{msg}\n"
    $stdout.puts(line); $stdout.flush
    begin
      File.open(LOG_FILE, 'a'){|f| f << line }
    rescue => e
      $stdout.puts "[WARN] log write failed: #{e}"
    end
  end

  def read_csv_tolerant(path)
    CSV.read(path, headers: true, encoding: 'bom|utf-8')
  rescue ArgumentError
    CSV.read(path, headers: true, encoding: 'CP1254:UTF-8')
  end
end

# List + selection
get '/' do
  list = files_sorted
  if list.empty?
    log_line "No CSV files under #{CSV_DIR}"
    halt 404, "Not Found CSV (#{CSV_DIR} boş)"
  end
  requested = params['path']
  csv_path  = requested ? File.join(CSV_DIR, requested) : latest_csv
  unless csv_path && File.exist?(csv_path)
    log_line "Requested file not found: #{requested.inspect}"
    return erb :list, locals: { files: list.map{|p| File.basename(p) }, msg: "Dosya yok: #{requested}" }
  end
  begin
    rows = read_csv_tolerant(csv_path)
  rescue => e
    log_line "Failed to read #{File.basename(csv_path)}: #{e.class}: #{e.message}"
    halt 500, "Not reading CSV file: #{e.class}: #{e.message}"
  end
  log_line "Served file: #{File.basename(csv_path)} (#{rows.size} satır)"
  erb :table, locals: {
    headers: rows.headers,
    rows: rows,
    filename: File.basename(csv_path),
    files: list.map{|p| File.basename(p) }
  }
end

# Display the last file directly.
get '/latest' do
  file = latest_csv
  halt 404, "Not Found CSV" unless file
  redirect "/?path=#{File.basename(file)}"
end

# Download/display the raw file.
get '/raw' do
  requested = params['path']
  file = requested ? File.join(CSV_DIR, requested) : latest_csv
  halt 404, "Not Found CSV" unless file && File.exist?(file)
  log_line "Raw download: #{File.basename(file)}"
  content_type 'text/csv'
  attachment File.basename(file) if params['download'] == '1'
  File.read(file)
end

__END__

@@list
<!doctype html><html lang="tr"><head><meta charset="utf-8" />
<title>CSV Listesi</title>
<style>body{font-family:system-ui,Arial,sans-serif;margin:24px;}ul{line-height:1.8;}
.msg{color:#b00;margin-bottom:12px;}</style></head><body>
<h1>Mevcut CSV Dosyaları</h1>
<p class="msg"><%= msg %></p>
<ul>
  <% files.reverse.each do |f| %>
    <li><a href="/?path=<%= f %>"><code><%= f %></code></a></li>
  <% end %>
</ul>
<p><a href="/latest">En son dosyayı aç</a></p>
</body></html>

@@table
<!doctype html><html lang="tr"><head><meta charset="utf-8" />
<title>CSV: <%= filename %></title>
<style>
body{font-family:system-ui,Arial,sans-serif;margin:24px;}
a{color:#06c;text-decoration:none;}a:hover{text-decoration:underline;}
table{border-collapse:collapse;width:100%;}
th,td{border:1px solid #ddd;padding:8px;}
th{background:#f5f5f5;text-align:left;position:sticky;top:0;}
.wrap{overflow:auto;max-height:80vh;margin-top:12px;}
.controls{margin-bottom:12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;}
input[type=text]{padding:6px;width:320px;}
select{padding:6px;}
</style></head><body>
<h1><%= filename %></h1>
<div class="controls">
  <form method="get">
    <label>File: </label>
    <select name="path">
      <% files.reverse.each do |f| %>
        <option value="<%= f %>" <%= 'selected' if f==filename %>><%= f %></option>
      <% end %>
    </select>
    <button type="submit">Upload</button>
  </form>
  <input id="q" type="text" placeholder="Search Table..." />
  <a href="/raw?path=<%= filename %>">Ham</a>
  <a href="/raw?path=<%= filename %>&download=1">Download</a>
  <a href="/">Liste</a>
</div>
<div class="wrap">
<table id="tbl">
  <thead><tr><% headers.each{|h| %><th><%= h %></th><% } %></tr></thead>
  <tbody>
    <% rows.each do |r| %>
      <tr><% headers.each{|h| %><td><%= r[h] %></td><% } %></tr>
    <% end %>
  </tbody>
</table>
</div>
<script>
document.getElementById('q').addEventListener('input', (e)=>{
  const val = e.target.value.toLowerCase();
  document.querySelectorAll('#tbl tbody tr').forEach(tr=>{
    tr.style.display = tr.innerText.toLowerCase().includes(val) ? '' : 'none';
  });
});
</script>
</body></html>
