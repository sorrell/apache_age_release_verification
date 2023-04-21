import os
import subprocess
import hashlib
import openai
import json
from pathlib import Path

# receive email in O365 to check Apache AGE release
# Use Power Automate to send email to gpt-3 to extract commit hash and fingerprint
# clone and check out commit hash
# check fingerprint
# if fingerprint matches, then download and check the checksum
# if checksum matches, then build and test
# if test passes, then email success of checks

PG_VERSION = os.getenv("PG_VERSION") or "12"
AGE_VERSION = os.getenv("AGE_VERSION") or "1.3.0"
RC_VERSION = os.getenv("RC_VERSION") or "rc0"
SIG_FINGERPRINT = os.getenv("FINGERPRINT").replace(' ', '')
COMMIT_HASH = os.getenv("COMMIT_HASH") 
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
APACHE_AGE_URL = f"https://dist.apache.org/repos/dist/dev/age/PG{PG_VERSION}/{AGE_VERSION}.{RC_VERSION}/"
GITHUB_AGE_URL = "https://github.com/apache/age.git"
AGE_DIRNAME = f"apache-age-{AGE_VERSION}"
AGE_PATH = Path(AGE_DIRNAME)
GIT_DIRNAME = f"{AGE_DIRNAME}-git"
GIT_PATH = Path(GIT_DIRNAME)
AGE_GZIP_FILENAME = f"apache-age-{AGE_VERSION}-src.tar.gz"
AGE_HASH_FILENAME = f"{AGE_GZIP_FILENAME}.sha512"
AGE_ASC_FILENAME = f"{AGE_GZIP_FILENAME}.asc"
SUCCESS_EMOJI="✅"
FAILURE_EMOJI="❌"
WORKING_EMOJI="💡"

# Function to print some of the global variables
def print_globals():
    print(f"PG_VERSION: {PG_VERSION}")
    print(f"AGE_VERSION: {AGE_VERSION}")
    print(f"RC_VERSION: {RC_VERSION}")
    print(f"SIG_FINGERPRINT: {SIG_FINGERPRINT}")
    print(f"COMMIT_HASH: {COMMIT_HASH}")
    print(f"OPENAI_API_KEY: sk-...{OPENAI_API_KEY[-3]}]")
    print(f"APACHE_AGE_URL: {APACHE_AGE_URL}")
    print(f"GITHUB_AGE_URL: {GITHUB_AGE_URL}")
    print(f"AGE_DIRNAME: {AGE_DIRNAME}")
    print(f"AGE_PATH: {AGE_PATH}")
    print(f"GIT_DIRNAME: {GIT_DIRNAME}")
    print(f"GIT_PATH: {GIT_PATH}")
    print(f"AGE_GZIP_FILENAME: {AGE_GZIP_FILENAME}")
    print(f"AGE_HASH_FILENAME: {AGE_HASH_FILENAME}")
    print(f"AGE_ASC_FILENAME: {AGE_ASC_FILENAME}")

def get_apache_release():
    # Download the gzip, SHA512 hash, and PGP signature files using curl
    for filename in (AGE_GZIP_FILENAME, AGE_HASH_FILENAME, AGE_ASC_FILENAME):
        download_command = f"curl -o {filename} {APACHE_AGE_URL}{filename}"
        subprocess.run(download_command, shell=True, check=True)

    # Decompress the gzip file
    decompress_command = f"tar xf {AGE_GZIP_FILENAME}"
    subprocess.run(decompress_command, shell=True, check=True)

# Function to verify the PGP signature of a file
def verify_pgp_signature(file_path):
    verify_command = f"gpg --verify {file_path}"
    output = subprocess.run(verify_command, shell=True, check=True, capture_output=True)
    
    openai.api_key = OPENAI_API_KEY

    prompt = f"Determine if this gpg output has a good signature. Return the response as json with the fields good_sig and fingerprint: {output.stderr.decode()}"
    print(f"Prompt: {prompt}")

    parameters = {
        "model": "gpt-3.5-turbo",
        "max_tokens": 250,
        "n": 1,
        "temperature": 0.5,
        "messages": [
            {
            "role": "system",
            "content": "You are a helpful assistant that is an expert in parsing gpg signatures and turning information into JSON objects. Your JSON should be lowercase, snakecase, and well-formed valid JSON. "
            },
            {
            "role": "user",
            "content": prompt
            }
        ]
    }
    response = openai.ChatCompletion.create(**parameters)
    text = response.choices[0].message.content
    json_response = json.loads(text)
    print(f"Response: {json_response}")
    if json_response["good_sig"] == "yes":
        print(f"{SUCCESS_EMOJI} PGP signature of {file_path} verified")
    if json_response["fingerprint"].replace(' ', '') == SIG_FINGERPRINT:
        print(f"{SUCCESS_EMOJI} PGP fingerprint of {file_path} verified")

# Function to verify the SHA512 hash of a file
def verify_sha512_hash(file_path):
    with open(file_path, 'r') as file:
        file_hash = file.read().split()[0]
    
    hasher = hashlib.sha512()
    with open(file_path[:-7], 'rb') as file:
        for chunk in iter(lambda: file.read(4096), b''):
            hasher.update(chunk)
    
    if file_hash == hasher.hexdigest():
        print(f"{SUCCESS_EMOJI} SHA512 hash of\n{file_hash}\n from {file_path} --> verified against {file_path[:-6]} to yield\n{hasher.hexdigest()}")
    else:
        print(f"{FAILURE_EMOJI} SHA512 hash of {file_path[:-7]} did not match")

# Function to clone a Git repository
def clone_repo(repo_url, target_directory, commit_hash=None):
    subprocess.run(["git", "clone", repo_url, target_directory])
    global GIT_PATH
    GIT_PATH = Path(GIT_DIRNAME)

    if commit_hash:
        # Change to the target directory and checkout the commit hash
        os.chdir(target_directory)
        subprocess.run(["git", "checkout", commit_hash])
        os.chdir("..")
        print(f"{SUCCESS_EMOJI} Git repo {repo_url} cloned to {target_directory} at commit {commit_hash}")
    else:
        print(f"{FAILURE_EMOJI} Git repo {repo_url} cloned to {target_directory} but no commit hash was provided")

# Function to check git tag
def check_git_tag(target_directory):
    # Change to the target directory and checkout the commit hash
    os.chdir(target_directory)
    # Check tag
    subprocess.run(["git", "fetch", "origin", "refs/tags/*:refs/tags/*"])
    tag = f"PG{PG_VERSION}/v{AGE_VERSION}-{RC_VERSION}"
    resp = subprocess.run(["git", "rev-list", "-n", "1", f"{tag}"], capture_output=True)
    tag_commit = resp.stdout.decode().strip()

    if tag_commit != COMMIT_HASH:
        print(f"{FAILURE_EMOJI} Error: Git tag commit {tag_commit} \ndoes not match commit hash {COMMIT_HASH}")
    else:
        print(f"{SUCCESS_EMOJI} Git tag {tag} verified")
    os.chdir("..")

# Function to calculate file checksum using SHA256
def calculate_checksum(file_path):
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as file:
        for chunk in iter(lambda: file.read(4096), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

def compare_checksums():
    # Compare the file checksums between the two clones
    match_count = 0
    mismatch_count = 0
    found_in_release_count = 0
    
    for file_a in AGE_PATH.glob("**/*"):
        if file_a.is_file():
            file_b = GIT_PATH / file_a.relative_to(AGE_PATH)
            
            if file_b.is_file():
                checksum_a = calculate_checksum(file_a)
                checksum_b = calculate_checksum(file_b)

                if checksum_a == checksum_b:
                    match_count += 1
                else:
                    print(f"{FAILURE_EMOJI} Mismatch: {file_a} and {file_b}")
                    mismatch_count += 1
            else:
                print(f"{FAILURE_EMOJI} File {file_b} not found in Git release, but in Apache release")
    
    print(f"Total matches: {match_count}")
    print(f"Total mismatches: {mismatch_count}")
    if mismatch_count == 0 and found_in_release_count == 0:
        print(f"{SUCCESS_EMOJI} All checksums and files match between Apache release and Git release")

# main
# print out the global vars calling function
print(f"{WORKING_EMOJI} Printing global variables...")
print_globals()
print(f"{WORKING_EMOJI} Getting Apache release...")
get_apache_release()
print(f"{WORKING_EMOJI} Verifying PGP signature...")
verify_pgp_signature(AGE_ASC_FILENAME)
print(f"{WORKING_EMOJI} Verifying SHA512 hash...")
verify_sha512_hash(AGE_HASH_FILENAME)
print(f"{WORKING_EMOJI} Cloning repo...")
clone_repo(GITHUB_AGE_URL, GIT_DIRNAME, COMMIT_HASH)
print(f"{WORKING_EMOJI} Checking git tag...")
check_git_tag(GIT_DIRNAME)
print(f"{WORKING_EMOJI} Comparing checksums...")
compare_checksums()

