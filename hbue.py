#!/usr/bin/python3

#
# HBUE, Antonio Ragagnin (2014)
#
# HBUE is an HTTP(S) Browse+Upload+Execute server.
# This tool runs an HTTP (or HTTPS) server, with the optional
# support of Basic Authentication. This server mainly furhishes
# a simple interface to upload, browse end execute files.
# Also, you can remove and download files.
#
# usage info: hbue.py --help
#

import http.server
import socketserver
import ssl
import os
import urllib.parse
import argparse
import base64
import cgi
import subprocess

def main():
	chunk = 1024
	folder = '.'
	certificate = None
	parser = argparse.ArgumentParser(description='HBUE is an HTTP(S) Browse+Upload+Execute server.\r\nAntonio Ragagnin (2014)')
	parser.add_argument('--listen', type=str, help='listening mask (default: localhost:4443)',default='localhost:4443')
	parser.add_argument('--execute', type=str,help='command to execute on clicked files.')
	parser.add_argument('--ssl', type=str, help='specify the .pem file to start an HTTPS server')
	parser.add_argument('--credentials', type=str, help='login:password string')
	parser.add_argument('--folder', type=str, help='folder to browse (default is current folder)',default='.')
	parser.add_argument('--chunk', type=str, help='chunk download size in Bytes (default: 1024)')
	args = parser.parse_args()
	listen_t = (args.listen.split(':')[0],int(args.listen.split(':')[1]))
	print ('server running on',listen_t,'...')
	httpd = http.server.HTTPServer(listen_t, MyHandler)
	#let's build an anonymous class and store it in the server
	base64credentials = None
	if(args.credentials!=None):base64credentials =base64.b64encode(bytes(args.credentials,'utf-8'))
	httpd.context = type("", (), dict(
                execute= args.execute, chunk=args.chunk,folder=args.folder,credentials=base64credentials
                ))() 
	if(args.ssl):
		httpd.socket = ssl.wrap_socket (httpd.socket, certfile=args.ssl, server_side=True)
	httpd.serve_forever()

	
class MyHandler(http.server.BaseHTTPRequestHandler):


	def make_index(self):	 
		self.send_response(200)
		self.send_header('Content-type','text/html')
		self.end_headers()
		page_tpl ="""<html>
		<head></head>
		<body>
		<h3>Upload a file</h3>
		<form method='POST' enctype='multipart/form-data'>
		Choose a file: <input type='file' name='upfile'/><br/>
		Upload to .%s<input type='text' name='path' value=''/><br/>
		<input type=submit value="Start upload"/>
		</form>
		<hr/>
		<h3>New folder</h3>
		<form method='POST' enctype='multipart/form-data'>
		Foldername .%s<input type='text' name='fname' value=''/><br/>
		<input type=submit value="Create it"/>
		</form>
		<hr/>
		<h3>Open a file</h3>
		<ul>""" 
		self.wfile.write(bytes(page_tpl % (os.sep,os.sep), 'UTF-8'))

		mypath = self.server.context.folder #os.path.abspath(relpath) # ; print abspath
		for dp, dn, filenames in os.walk(mypath):
			self.wfile.write(bytes("\t\t<li><a href=\"/delete?%s\">del</a>  %s</li>\n" % (dp,dp) , 'UTF-8'))
			for f in filenames:
				f = os.path.join(dp, f) 
				self.wfile.write(bytes("\t\t<li><a href=\"/delete?%s\">del</a>  <a href=\"/execute?%s\">ex</a>  <a href=\"/download?%s\">%s</a></li>\n" % (urllib.parse.unquote(f),urllib.parse.unquote(f),urllib.parse.unquote(f),f) , 'UTF-8'))

		page_tpl="""</ul>
		</body>
	</html>"""	 
		self.wfile.write(bytes(page_tpl, 'UTF-8'))
	  
	def do_AUTHHEAD(self):
		header = self.headers['Authorization']
		if not self.server.context.credentials:
			return True
		if header == None or header != 'Basic '+str(self.server.context.credentials.decode("utf-8")):
			self.send_response(401)
			self.send_header('WWW-Authenticate', 'Basic realm=\"HBUE login\"')
			self.send_header('Content-type', 'text/html')
			self.end_headers()
			return False	
		else:
			return True

			
	def do_GET(self):
		if not self.do_AUTHHEAD():
			return
		try:
			pages = self.path.split('?')
			if(len(pages)==1):
				page = pages[0]
				file = ''
			else:
				page = pages[0]
				file = '?'.join(pages[1:])
			if page == '/' :
				self.make_index()
				return	 
			elif page == '/delete' :	 
				filepath = urllib.parse.unquote(file) # remove leading '/'
				if os.path.isdir(filepath):
					print('deleting folder',filepath);
					os.rmdir(self.server.context.folder +os.sep+filepath)
				else:
					os.remove(self.server.context.folder +os.sep+filepath)
				self.make_index()
				return	 

			elif page == '/execute' :	
				filepath = urllib.parse.unquote(file) # remove leading '/'
				fullname = self.server.context.folder +os.sep+filepath
				if(not self.server.context.execute):
					print('executing ',' '.join([fullname]));
					subprocess.Popen([fullname])
				else:
					print('executing ',' '.join([ self.server.context.execute,fullname]));
					subprocess.Popen([ self.server.context.execute,fullname])
				self.make_index()
				return	 

			elif page == '/download' :	 
				filepath = urllib.parse.unquote(file) # remove leading '/'	 
				if self.path == '/favicon.ico' :	 
					f = open( filepath, 'rb' ) 
				else:
					f = open( self.server.context.folder +os.sep+filepath, 'rb' ) 

				self.send_response(200)
				self.send_header('Content-type','application/octet-stream')
				self.send_header('Content-Disposition','attachment; filename="%s"' % os.path.basename(filepath))
				
				self.end_headers()
				for piece in MyHandler.read_in_chunks(f,self.server.context.chunk):
					self.wfile.write(bytes(piece))
				f.close()
				return
			print ('nope: ',self.path)
			return # be sure not to fall into "except:" clause ?	   
				
		except IOError as e :  
			# debug	 
			print (e)
			self.send_error(404,'Error: %s' % str(e))
	 
	def read_in_chunks(file_object, chunk_size):
		while True:
			data = file_object.read(chunk_size)
			if not data:
				break
			yield data

	def do_POST(self):
			if not self.do_AUTHHEAD():
				 return
		# global rootnode ## something remained in the orig. code	 
			ctype, pdict = cgi.parse_header(self.headers['content-type'])	 
			if ctype == 'multipart/form-data' :	 
				# using cgi.FieldStorage instead, see 
				# http://stackoverflow.com/questions/1417918/time-out-error-while-creating-cgi-fieldstorage-object	 
				fs = cgi.FieldStorage( fp = self.rfile, 
									   headers = self.headers, # headers_, 
									   environ={ 'REQUEST_METHOD':'POST' } # all the rest will come from the 'headers' object,	 
									   # but as the FieldStorage object was designed for CGI, absense of 'POST' value in environ	 
									   # will prevent the object from using the 'fp' argument !	 
									 )
				## print 'have fs'	
			else: raise Exception("Unexpected POST request")
			if(fs.getvalue("fname")):		
				new_folder =self.server.context.folder+os.sep+ fs.getvalue("fname")
				if not os.path.isdir(new_folder):
					print ('creating folder '+new_folder)
					os.makedirs(new_folder)
				self.make_index()
				return
					
			fs_up = fs['upfile']
			folder = fs.getvalue("path")
			filename = os.path.split(fs_up.filename)[1] # strip the path, if it presents	 
			fullname = self.server.context.folder
			fullname +=os.sep
			fullname +=folder
			fullname +=os.sep
			fullname +=filename #os.path.join(folder,os.sep+filename)
			print (' uploading',fullname)
			
			# check for copies :	 
			if os.path.exists( fullname ):	 
				fn,fe = os.path.splitext(fullname)
				fullname_test = fn + '.copy'+fe
				i = 2
				while os.path.exists( fullname_test ):
					fullname_test = fn + '.copy(%d)' % i +fe
					i += 1
				fullname = fullname_test
				
			if not os.path.exists(fullname):
				with open(fullname, 'wb') as o:
					for piece in MyHandler.read_in_chunks(fs_up.file,self.server.context.chunk):
						o.write( piece )	 
			self.make_index()

if __name__ == "__main__": 
	main()
