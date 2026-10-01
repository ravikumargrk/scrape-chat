from app import await_rdp_load, connect_browser

await_rdp_load()

_pw, _context, page, composer = connect_browser()
pass
print(_context)
