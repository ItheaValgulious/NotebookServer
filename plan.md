# Notebook Server

default response means only a json obj with status:succeed/failed

## User Operation

tokens should be generated when the user is signin/signup and be expired when user signout or after specific time

- Signup: post /signup
  - json body:username,password
  - response:
    - status: succeed/failed
    - token: the token of user
- signin: post /signin
  - json body:username,password
  - response:
    - status: succeed/failed
    - token: the token of user
- signout:
  - json body:token
  - response:
    - token: ""
    - status: succeed/failed

## File Operation

the server should maintain a file system for every user and supports the below operations:

the file system should be organized by the following way:
data/username/file.json: contains the file system structure without the specific content of a file
data/username/{fileid}: the content of a file

- read folder: get /file/(path) if the path is a folder
  - query params:token
  - return the file structure by json of folder in path.
  - response(json):
    - status: succeed/failed
    - data: a object with the following attributes:
      - type:"folder" or "file"
      - path:the path in the file system
      - id: a unique id of file
      - children: if type=="folder",children is an array of child folders/files; else the children is []
- read file: get/file/(path) if the path is a file
  - query params:token
  - return the content
  - response(raw):
    - file's content
- write: post /file/(path)
  - query params:token
  - body:file's content
  - if the file does not exists,create it
- rename: post/file/(oldpath)
  - query params:newpath,token
  - default response
- delete: delete/file/(oldpath)
  - query params:token
  - default response

## Picture Operation

- picture upload: post /picture/upload
  - query params:token
  - body:img's content
  - response:
    - status
    - url(/picture/{picture_id})
- picture get: get /picture/{picture_id}
  - query params:token
  - response:the picture


you should read the requirements and realize it with python, use fastapi framework.
The file can be stored directly in the folder "data"
don't use jose or passlib and so on. you can generate token by yourself.



I had had a server and you should generate a html page for the api testing
