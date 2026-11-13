# CodeAlpha — Cloud Computing Internship, Task 1

## Data Redundancy Removal System

**Track (correct name): Cloud Computing** — not "Cloud Security".
CodeAlpha has a Cyber Security track, but no Cloud Security track, so
on your CV / LinkedIn / mentor messages this internship is
**"Cloud Computing Internship"**. The security angle comes from what
you build, not the track name.

**Task (from the CodeAlpha PDF):** build a system that identifies and
classifies data as redundant or false positive, validates new data
against existing data, prevents duplicates entering the cloud
database, and appends only unique + verified entries.

**Stack:** Python + AWS DynamoDB, region **ap-southeast-2 (Sydney)**,
IAM user `talal-admin` — the same setup as your AWS Labs 01–06.
**Cost: $0** — a few KB in DynamoDB on-demand (PAY_PER_REQUEST),
inside the Free Tier. Table is deleted after the run.

## How it works

| New record | Verdict | Stored? |
|---|---|---|
| Passes validation, new hash, new email | UNIQUE | Yes |
| SHA-256 hash already in the table | REDUNDANT (exact duplicate) | No — blocked |
| Same email, different details | FALSE POSITIVE | No — held for review, not auto-appended or auto-deleted |
| Bad email / phone / missing name | INVALID | No — rejected |

Hashing uses a canonical form (keys sorted, text stripped +
lower-cased), so ` Ali ` and `ali` count as the same record.

## Run it — one command at a time (Windows PowerShell)

**Step 1 — check boto3 (Python se AWS chalane ke liye chahiye):**
```powershell
python -c "import boto3; print(boto3.__version__)"
```
Version number aaye to theek hai. Error aaye to:
```powershell
pip install boto3
```

**Step 2 — logic check, no AWS needed:**
```powershell
python redundancy.py --local
```
Expected output: `UNIQUE=2, REDUNDANT=2, FALSE POSITIVE=1, INVALID=1`,
database mein 2 records (Ahmed Raza + Bilal Hussain).

**Step 3 — real cloud run (DynamoDB table banegi, Sydney):**
```powershell
python redundancy.py --aws
```
Table ka naam: `codealpha-redundancy-demo`. Dobara chalao ge to
records pehle se stored milenge — duplicate wali lines REDUNDANT
aayengi, yehi proof hai ke system kaam kar raha hai.

**Step 4 — cleanup (table delete karo, $0 rule):**
```powershell
python redundancy.py --aws --cleanup
```

## GitHub (CodeAlpha ki requirement)

Repo ka naam PDF ke rule ke mutabiq: **`CodeAlpha_DataRedundancyRemovalSystem`**
(`CodeAlpha_ProjectName` format). Is folder ki files upload karo —
`redundancy.py`, `README.md`, `requirements.txt`, `.gitignore`.
**Koi credential commit mat karna** — `.env` / AWS keys repo mein
nahi hain, boto3 laptop par pehle se configured profile use karta hai.

## Submission (PDF ke mutabiq)

1. LinkedIn par internship status share karo, **@CodeAlpha** tag karo.
2. Code GitHub repo mein daalo (upar wala naam).
3. Project ki **video explanation** LinkedIn par post karo, GitHub
   repo link ke saath.
4. Submission Form se submit karo — form tumhare **WhatsApp group**
   mein share hoga. Sirf usi form se submit karna hai.
5. Certificate ke liye **kam se kam 2 tasks** zaroori hain — 1 task
   incomplete mana jayega.

## Agla — Task 2 aur Task 3 (plan, abhi code nahi)

- **Task 2 — SQL Injection Defense:** Flask app EC2 par. Pehle
  vulnerable version (injection kaam karta hai), phir secure version —
  parameterized queries + AES-256 encryption. Ye tumhare goal se
  sab se zyada jura hai.
- **Task 3 — Bus Pass System:** Flask booking app EC2 + DynamoDB.
  Scaling ke liye Auto Scaling + Load Balancer ka design (bina paid
  cheez chalaye).
- **Task 4 (chatbot) skip** — chatbot tum pehle se banate ho, naya
  kuch nahi seekho ge.
- **Order: 1 → 2 → 3.** Har project par aik security layer lagao
  (S3 public-access block, security groups mein sirf zaroori ports,
  IAM least-privilege) — yehi cheez Cloud Computing internship ko
  Cloud Security profile banati hai.
