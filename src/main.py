import uuid
import json
import os
from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse
from fastapi import File, UploadFile
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

# Users file
USERS_FILE = "data/users.json"
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump({}, f)

# Tokens in memory: token -> username
tokens = {}

def load_users():
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

def get_username(token):
    return tokens.get(token)

def load_structure(username):
    structure_file = f"data/{username}/file.json"
    if not os.path.exists(structure_file):
        raise HTTPException(404, "User structure not found")
    with open(structure_file, "r") as f:
        return json.load(f)

def save_structure(username, structure):
    with open(f"data/{username}/file.json", "w") as f:
        json.dump(structure, f)

def find_node(structure, path):
    if path == "/" or path == "":
        return structure
    segments = [s for s in path.strip("/").split("/") if s]
    current = structure
    for seg in segments:
        found = None
        for child in current.get("children", []):
            if child["path"].split("/")[-1] == seg:
                found = child
                break
        if not found:
            return None
        current = found
    return current

def create_parents(structure, parent_path, username):
    segments = [s for s in parent_path.strip("/").split("/") if s]
    current = structure
    current_path = "/"
    for seg in segments:
        found = None
        for child in current["children"]:
            if child["path"].split("/")[-1] == seg:
                found = child
                break
        if found:
            if found["type"] != "folder":
                raise HTTPException(400, "Path conflict: not a folder")
            current = found
            current_path = found["path"]
        else:
            new_id = uuid.uuid4().hex
            new_path = current_path + ("" if current_path == "/" else "/") + seg
            new_node = {
                "type": "folder",
                "path": new_path,
                "id": new_id,
                "children": []
            }
            current["children"].append(new_node)
            current = new_node
            current_path = new_path
    return current

def update_paths(node, new_path):
    node["path"] = new_path
    for child in node["children"]:
        child_new_path = new_path + "/" + child["path"].split("/")[-1]
        update_paths(child, child_new_path)

def delete_recursive(username, node):
    for child in node["children"]:
        if child["type"] == "file":
            content_path = f"data/{username}/{child['id']}"
            if os.path.exists(content_path):
                os.remove(content_path)
        else:
            delete_recursive(username, child)
    # Delete own content if file, but folders don't have content files

@app.get("/check")
async def check_token(token: str = Query(None)):
    username = get_username(token)
    if username:
        return {"status": "succeed", "username": username}
    else:
        return {"status": "failed"}

@app.post("/signup")
async def signup(request: Request):
    try:
        body = await request.json()
    except:
        return {"status": "failed"}
    username = body.get("username")
    password = body.get("password")
    if not username or not password:
        return {"status": "failed"}
    users = load_users()
    if username in users:
        return {"status": "failed"}
    users[username] = password
    save_users(users)
    # Create user dir
    user_dir = f"data/{username}"
    os.makedirs(user_dir, exist_ok=True)
    os.makedirs(f"{user_dir}/pictures", exist_ok=True)
    # Create initial structure
    structure = {
        "type": "folder",
        "path": "/",
        "id": "root",
        "children": []
    }
    save_structure(username, structure)
    # Generate token
    token = uuid.uuid4().hex
    tokens[token] = username
    return {"status": "succeed", "token": token}

@app.post("/signin")
async def signin(request: Request):
    try:
        body = await request.json()
    except:
        return {"status": "failed"}
    username = body.get("username")
    password = body.get("password")
    if not username or not password:
        return {"status": "failed"}
    users = load_users()
    if username in users and users[username] == password:
        token = uuid.uuid4().hex
        tokens[token] = username
        return {"status": "succeed", "token": token}
    return {"status": "failed"}

@app.post("/signout")
async def signout(request: Request):
    try:
        body = await request.json()
    except:
        return {"token": "", "status": "failed"}
    token = body.get("token")
    if token in tokens:
        del tokens[token]
        return {"token": "", "status": "succeed"}
    return {"token": "", "status": "failed"}

@app.get("/file/{path:path}")
async def read(path: str, token: str = Query(None)):
    username = get_username(token)
    if not username:
        raise HTTPException(401, "Invalid token")
    structure = load_structure(username)
    node = find_node(structure, path)
    if not node:
        raise HTTPException(404, "Not found")
    if node["type"] == "folder":
        return {"status": "succeed", "data": node}
    elif node["type"] == "file":
        file_path = f"data/{username}/{node['id']}"
        if not os.path.exists(file_path):
            raise HTTPException(404, "Content not found")
        with open(file_path, "r") as f:
            content = f.read()
        return PlainTextResponse(content)
    else:
        raise HTTPException(400, "Unknown type")

@app.post("/file/{path:path}")
async def write(path: str, request: Request, token: str = Query(None)):
    username = get_username(token)
    if not username:
        raise HTTPException(401, "Invalid token")
    content_bytes = await request.body()
    try:
        content = content_bytes.decode("utf-8")
    except:
        raise HTTPException(400, "Content must be text")
    structure = load_structure(username)
    node = find_node(structure, path)
    if node:
        if node["type"] == "file":
            # Overwrite
            with open(f"data/{username}/{node['id']}", "w") as f:
                f.write(content)
            return {"status": "succeed"}
        else:
            raise HTTPException(400, "Cannot write to folder")
    # Create new file, create parents if needed
    parent_path, name = os.path.split(path)
    if not name:
        raise HTTPException(400, "Invalid path")
    parent = find_node(structure, parent_path)
    if not parent:
        parent = create_parents(structure, parent_path, username)
    if parent["type"] != "folder":
        raise HTTPException(400, "Parent not a folder")
    # Check if name exists
    for child in parent["children"]:
        if child["path"].split("/")[-1] == name:
            raise HTTPException(409, "Name already exists")
    # Create new file
    new_id = uuid.uuid4().hex
    new_path = (parent["path"] if parent["path"] == "/" else parent["path"] + "/") + name
    new_node = {
        "type": "file",
        "path": new_path,
        "id": new_id,
        "children": []
    }
    parent["children"].append(new_node)
    save_structure(username, structure)
    with open(f"data/{username}/{new_id}", "w") as f:
        f.write(content)
    return {"status": "succeed"}

@app.post("/rename/file/{oldpath:path}")
async def rename(oldpath: str, newpath: str = Query(None), token: str = Query(None)):
    username = get_username(token)
    if not username:
        raise HTTPException(401, "Invalid token")
    if oldpath == "/" or not newpath:
        return {"status": "failed"}
    structure = load_structure(username)
    node = find_node(structure, oldpath)
    if not node:
        return {"status": "failed"}
    # Find old parent and remove
    old_parent_path, old_name = os.path.split(oldpath)
    old_parent = find_node(structure, old_parent_path)
    if not old_parent:
        return {"status": "failed"}
    old_parent["children"] = [c for c in old_parent["children"] if c["path"].strip('/') != oldpath.strip('/')]
    # Update paths
    update_paths(node, newpath)
    # Find/create new parent
    new_parent_path, new_name = os.path.split(newpath)
    new_parent = find_node(structure, new_parent_path)
    if not new_parent:
        new_parent = create_parents(structure, new_parent_path, username)
    if new_parent["type"] != "folder":
        return {"status": "failed"}
    # Check name conflict
    for child in new_parent["children"]:
        if child["path"].split("/")[-1] == new_name:
            return {"status": "failed"}
    # Add to new parent
    new_parent["children"].append(node)
    save_structure(username, structure)
    return {"status": "succeed"}

@app.delete("/file/{path:path}")
async def delete(path: str, token: str = Query(None)):
    username = get_username(token)
    if not username:
        raise HTTPException(401, "Invalid token")
    if path == "/":
        return {"status": "failed"}
    structure = load_structure(username)
    node = find_node(structure, path)
    if not node:
        return {"status": "failed"}
    # Delete contents
    if node["type"] == "file":
        content_path = f"data/{username}/{node['id']}"
        if os.path.exists(content_path):
            os.remove(content_path)
    else:
        delete_recursive(username, node)
    # Remove from parent
    parent_path, _ = os.path.split(path)
    parent = find_node(structure, parent_path)
    if parent:
        parent["children"] = [c for c in parent["children"] if c["path"].strip('/') != path.strip('/')]
    save_structure(username, structure)
    return {"status": "succeed"}

@app.post("/picture/")
async def upload_picture(token: str = Query(None), img: UploadFile = File(...)):
    username = get_username(token)
    if not username:
        raise HTTPException(401, "Invalid token")
    if not img:
        return {"status": "failed"}
    pic_id = username+'_'+uuid.uuid4().hex
    pic_dir = f"data/pictures"
    # 确保目录存在
    os.makedirs(pic_dir, exist_ok=True)
    pic_path = f"{pic_dir}/{pic_id}"
    with open(pic_path, "wb") as f:
        f.write(await img.read())
    url = f"/picture/{pic_id}"
    return {"status": "succeed", "url": url}

@app.get("/picture/{picture_id}")
async def get_picture(picture_id: str):
    pic_path = f"data/pictures/{picture_id}"
    if not os.path.exists(pic_path):
        raise HTTPException(404, "Picture not found")
    return FileResponse(pic_path, media_type="image/jpeg")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)