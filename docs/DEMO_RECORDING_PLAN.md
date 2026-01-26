# Demo Recording Plan: Bedsheet End-to-End Multi-Cloud Deployment

## Goal
Record a 3-4 minute demo showing Bedsheet's "Build Once, Deploy Anywhere" by deploying the investment advisor agent to Local, GCP, and AWS from the same codebase.

## 🔧 IMPLEMENTATION: EXACT FILE CHANGES

### File 1: bedsheet/cli/main.py
**Line 372** - Change GCP default model

**Current**:
```python
model="gemini-2.5-flash",
```

**New**:
```python
model="gemini-3-flash-preview",
```

**Why**: Update to Gemini 3 Flash Preview for demo

---

### File 2: README.md (Already Done)
**Lines 381-387** - Add GCP deployment deep dive link

**Status**: ✅ Already completed in this session

---

### File 3: CLAUDE.md (Already Done)
**Lines 59-65** - Add GCP deployment deep dive to docs table

**Status**: ✅ Already completed in this session

---

## That's It!

Only ONE file edit needed: bedsheet/cli/main.py line 372

After this change:
- Copy this plan to `docs/DEMO_RECORDING_PLAN.md` (for project reference)
- Commit all changes
- User will do manual demo recording steps (no further code changes needed)

---

## VERIFICATION

After implementation:
```bash
# Verify the model change
grep "gemini-3-flash-preview" bedsheet/cli/main.py

# Test that init works
bedsheet init test-demo --target gcp
grep "gemini-3-flash-preview" test-demo/bedsheet.yaml
rm -rf test-demo

# Verify plan is saved
ls -la docs/DEMO_RECORDING_PLAN.md
```

## Demo Flow (3-4 Minutes Total)

### Scene 1: Init Project (30s)
```bash
# Create new project with local target
bedsheet init investment-demo --target local
cd investment-demo
ls -la
```

**Shows**:
- Project scaffolding
- Generated files (bedsheet.yaml, pyproject.toml, agents/)
- Sample assistant agent

**Voiceover**: "Bedsheet scaffolds a complete agent project in seconds."

---

### Scene 2: Add Investment Advisor Agents (30s)
```bash
# Copy investment advisor from examples
cp ../examples/investment-advisor/agents.py agents/
cat agents.py | head -50  # Show structure

# Edit bedsheet.yaml to configure multi-target deployment
# (Show in editor - add GCP and AWS targets)
```

**Manual Edit to bedsheet.yaml** (show in editor):
```yaml
version: '1.0'
name: investment-demo
agents:
  - name: InvestmentAdvisor
    module: agents
    class_name: InvestmentAdvisor
    description: Multi-agent investment advisor

target: local

targets:
  local:
    port: 8000
    hot_reload: true

  gcp:
    project: YOUR_PROJECT_ID  # Your actual GCP project
    region: europe-west1
    cloud_run_memory: 1Gi
    model: gemini-3-flash-preview

  aws:
    region: us-east-1
    bedrock_model: anthropic.claude-sonnet-4-5-v2:0
    lambda_memory: 512
    enable_delegate_for_supervisors: false
```

**Voiceover**: "We configure three deployment targets in bedsheet.yaml: local, GCP, and AWS. Same agent code, three environments."

---

### Scene 3: Run Locally (45s)
```bash
# Generate local deployment
bedsheet generate --target local

# Build and run
cd deploy/local
export ANTHROPIC_API_KEY=sk-ant-...
make build
make run
```

**Browser Recording**:
1. Open `http://localhost:8000`
2. Type: "Should I buy NVIDIA stock?"
3. Show event stream panel (parallel delegation to 3 agents)
4. Show final response with real stock data

**Voiceover**: "Local deployment includes a debug UI with real-time event streaming. You see every tool call and agent handoff."

---

### Scene 4: Deploy to GCP (45s)
```bash
# Generate GCP deployment
cd ../..  # Back to project root
bedsheet generate --target gcp

# Deploy to Cloud Run
cd deploy/gcp
make init
make deploy  # Shows Terraform output
```

**Wait for deployment** (~2-3 min - may need to speed up video or cut)

**Browser Recording**:
1. `make ui` to open ADK Dev UI
2. Send same query
3. Show response

**Voiceover**: "Deploy to Google Cloud Platform with Terraform. The ADK provides a production-ready debug UI."

---

### Scene 5: Deploy to AWS (60s)
```bash
# Generate AWS deployment
cd ../..
bedsheet generate --target aws

# Deploy with CDK
cd deploy/aws
make setup
make deploy  # Shows CDK output
```

**Wait for deployment** (~3-5 min - may need to speed up video or cut)

**Extract agent ID and test**:
```bash
export BEDROCK_AGENT_ID=<from-cdk-output>
python debug-ui/server.py
```

**Browser Recording**:
1. Open `http://localhost:8080`
2. Send same query
3. Show collaborator events

**AWS Console** (optional if time permits):
1. Navigate to Bedrock → Agents
2. Show agent with 3 collaborators
3. Test in console

**Voiceover**: "AWS deployment uses native Bedrock agents. Same code, three clouds."

---

## Time-Saving Strategies

### Option A: Speed Up Deployments in Post
- Record full deployments
- Speed up video 4-8x during "deploying..." phases
- Resume normal speed for UI interactions

### Option B: Pre-Deploy + Show Artifacts
- Deploy GCP/AWS beforehand
- Show generated files and Terraform/CDK commands during recording
- Cut to pre-deployed UI interactions
- More realistic timing for demo

### Recommended: Hybrid Approach
1. Show `bedsheet generate` commands (fast, no waiting)
2. Show first few lines of deployment output
3. Cut/speed up to deployment complete
4. Show UI interactions at normal speed

---

## Pre-Recording Checklist

### Code Changes
- [ ] Update bedsheet/cli/main.py:372 to `model="gemini-3-flash-preview"`
- [ ] Commit and test: `bedsheet init test --target gcp` should show gemini-3-flash-preview in yaml

### Environment Setup
- [ ] `export ANTHROPIC_API_KEY=sk-ant-...`
- [ ] GCP: `gcloud auth login` and `gcloud auth application-default login`
- [ ] GCP: Note your project ID for bedsheet.yaml
- [ ] AWS: `aws configure` or `AWS_PROFILE=personal`
- [ ] AWS: `cdk bootstrap` if not already done
- [ ] Docker: Ensure running

### Dry Run Tests
- [ ] Test: `bedsheet init test-demo --target local` works
- [ ] Test: Copy agents.py from examples/investment-advisor
- [ ] Test: Edit bedsheet.yaml to add GCP/AWS targets
- [ ] Test: `bedsheet generate --target local` works
- [ ] Test: Local deployment builds and runs
- [ ] Test: `bedsheet generate --target gcp` works
- [ ] Test: GCP deployment completes successfully
- [ ] Test: `bedsheet generate --target aws` works
- [ ] Test: AWS deployment completes successfully
- [ ] Time each step to estimate video length

### Recording Setup
- [ ] Clean terminal (clear history, set good font size)
- [ ] Editor ready for bedsheet.yaml edits (VSCode/Cursor with good theme)
- [ ] Browser windows prepared (localhost:8000, localhost:8080)
- [ ] AWS Console logged in and on Bedrock Agents page
- [ ] Screen recording tool ready (Poindeo or similar)
- [ ] Voiceover script prepared

---

## Critical Files

### Investment Advisor Source
- `examples/investment-advisor/agents.py` - The multi-agent code to copy

### Generated Files to Show
- `deploy/local/Dockerfile` - Docker setup
- `deploy/local/docker-compose.yaml` - Service config
- `deploy/gcp/main.tf` - Terraform infrastructure
- `deploy/aws/app.py` - CDK stack

---

## Contingency Plans

### If GCP Deployment Fails
- Skip GCP, show Local + AWS only
- Still demonstrates multi-target capability
- Adjust voiceover to "deploy to cloud"

### If AWS Deployment Times Out
- Have pre-deployed AWS agent ready
- Jump to debug UI / console interaction
- Mention deployment in voiceover

### If Local Docker Build Fails
- Have pre-built image ready
- `docker load < prebuilt.tar`
- Continue with demo

---

## Success Criteria

✅ Demo shows:
1. `bedsheet init` scaffolding
2. Multi-agent code structure (supervisor + collaborators)
3. bedsheet.yaml multi-target configuration
4. Local deployment with debug UI
5. GCP deployment with ADK UI
6. AWS deployment with debug UI or console
7. Real data flowing (stock prices, news)
8. Event streaming visibility

✅ Total duration: 3-4 minutes (+ speedups for deployment waits)
✅ Clear voiceover explaining each step
✅ No visible errors during recording
