# VRC — Verifiable Reasoning Credential

## What It Does

Paste any text making claims — a position paper, AI-generated analysis, policy proposal, argument — and get back:

1. **Extracted claims** identified by Claude as discrete propositions
2. **Attack/support relations** between those claims
3. **Formal argumentation analysis** using Dung's abstract argumentation framework
4. **Visual argument map** showing which claims survive formal challenge
5. **Downloadable VRC** — a JSON credential containing the full reasoning structure

The key insight: the formal computation of which claims are defensible is *different* from an LLM's opinion about which claims are strong. That gap is the demonstration.

## Architecture

```
User pastes text
    ↓
Claude API (Sonnet) extracts claims + attack relations
    ↓
Dung solver computes grounded/preferred/stable extensions
    ↓
D3.js renders argument graph (green=accepted, red=rejected, yellow=undecided)
    ↓
VRC JSON available for download (W3C VC-shaped, content-hashed)
```

## Files

| File | Purpose |
|------|---------|
| `app.py` | Flask web app — routes, Claude API integration, VRC builder |
| `dung_solver.py` | Pure Python Dung argumentation framework solver |
| `templates/index.html` | Frontend — D3.js force-directed graph, dark technical aesthetic |
| `requirements.txt` | Python dependencies (flask, anthropic, gunicorn) |
| `cloudformation.yaml` | AWS CloudFormation template for one-click deployment |

## Deploy to AWS

### Prerequisites

- AWS account with CLI configured
- An Anthropic API key
- An S3 bucket

### Steps

**1. Upload the artifact to S3**

```bash
aws s3 cp vrc.tar s3://YOUR-BUCKET/vrc.tar
```

**2. Create the CloudFormation stack**

```bash
aws cloudformation create-stack \
  --stack-name vrc \
  --template-body file://cloudformation.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters \
    ParameterKey=S3Bucket,ParameterValue=YOUR-BUCKET \
    ParameterKey=S3Key,ParameterValue=vrc.tar \
    ParameterKey=AnthropicApiKey,ParameterValue=sk-ant-YOUR-KEY \
    ParameterKey=KeyPairName,ParameterValue=YOUR-KEYPAIR
```

**3. Wait for stack creation (~3 minutes)**

```bash
aws cloudformation wait stack-create-complete --stack-name vrc
```

**4. Get the URL**

```bash
aws cloudformation describe-stacks --stack-name vrc \
  --query 'Stacks[0].Outputs[?OutputKey==`WebURL`].OutputValue' --output text
```

Open that URL in your browser. Done.

### Cost

- t3.micro: ~$8.50/month (or free tier eligible)
- Claude API: ~$0.003-0.01 per analysis (Sonnet, typically 1-2K tokens)

### Troubleshooting

SSH in and check:

```bash
ssh -i your-key.pem ubuntu@INSTANCE-IP

# Check service status
sudo systemctl status vrc

# Check logs
sudo journalctl -u vrc -f

# Check setup log
cat /var/log/vrc-setup.log
```

## Run Locally

```bash
cd vrc
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python app.py
# Open http://localhost:8080
```

## The VRC JSON Structure

The downloadable credential follows W3C Verifiable Credential shape:

```json
{
  "@context": ["https://www.w3.org/2018/credentials/v1", "https://vrc.example/v1"],
  "type": ["VerifiableCredential", "VerifiableReasoningCredential"],
  "credentialSubject": {
    "argumentationFramework": {
      "arguments": [...],
      "attacks": [...],
      "supports": [...]
    },
    "extensions": {
      "grounded": ["c1", "c3"],
      "preferred": [["c1", "c3", "c5"]],
      "stable": [["c1", "c3", "c5"]]
    },
    "argumentStatus": {
      "c1": "accepted",
      "c2": "rejected",
      "c3": "accepted"
    }
  },
  "proof": {
    "type": "ContentIntegrityHash",
    "contentHash": "sha256:..."
  }
}
```

**Grounded extension**: Most conservative — claims that survive ALL attacks. If it's in the grounded set, there's no formal basis for rejecting it.

**Preferred extensions**: Maximal coherent worldviews. Multiple preferred extensions = genuinely contested positions where reasonable people can disagree.

**Stable extensions**: Complete worldviews that account for every claim (accept or attack it). No stable extension = the argument has irresolvable tensions.

## What This Demonstrates

The VC ecosystem verifies **who said something** and **whether it was tampered with**. VRC verifies **whether the reasoning is internally coherent**. That's the gap nobody's filling.

## Teardown

```bash
aws cloudformation delete-stack --stack-name vrc
```
