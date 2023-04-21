# AGE Verifier
This is a proof-of-concept to test using OpenAI, Power Automate, and GitHub Actions to verify a release of the Apache AGE project.

## General workflow
1.  Receive email in O365 to Vote/check Apache AGE release
2.  Use Power Automate to handle email  
    1.  Filter on subject “[VOTE] Apache AGE”  
    2.  Call OpenAI API with body of email to extract the follow as `pa_json` payload  
        1.  commit hash for release
        2.  gpg fingerprint
        3.  version of Postgres
        4.  version of AGE
        5.  release candidate #
    3.  Trigger Github Action to verify release with `pa_json` payload from above step
3.  Github Action is invoked
    1.  Run Job 1 – handling high-level checks
        1.  Build Dockerfile in repo
        2.  Run Container (compare.py)
            1.  Download official Apache AGE release (directory A), sha512, and signature .asc file
            2.  Verify signature
                  1.  Call OpenAI API to return as `sig_json` 
                      1.  Good_signature = True/False
                      2.  Fingerprint of signature
                  2.  Check `sig_json.fingerprint` from above against `pa_json`.fingerprint
            3.  Verify sha512 sum
            4.  Clone AGE git repo (directory B) and check out commit hash
                1.  Check git tag
            5.  Compare all files between directories A and B
                1.  Compare checksum
                2.  Compare files present in A not in B
    2.  Run Job 2 - smoke tests in Postgres / Apache AGE
        1.  Clone AGE repo
        2.  Copy custom commands to run in container from Github Gist
        3.  Build Dockerfile, run container
            1.  Run smoketests
