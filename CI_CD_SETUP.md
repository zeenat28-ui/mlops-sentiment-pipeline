# 🚀 CI/CD Setup Guide - MLOps Sentiment Pipeline

## 📋 Overview

Yeh pipeline tumhari sentiment classifier model ko automated testing aur deployment ke sath production-ready banati hai.

## 🎯 Pipeline Stages

### 1. **CI Checks** (`ci.yml`) - PR par
- ✅ Ruff linting
- ✅ Unit tests (pytest)
- ✅ Bundle validation for integration_test target
- **Trigger**: Har pull request par automatically

### 2. **Deploy & Test** (`deploy-test.yml`) - Main branch par
- ✅ Production registry snapshot (before)
- ✅ Bundle deploy to integration_test target
- ✅ Integration job execution (`retrain_sentiment`)
- ✅ Production registry snapshot (after)
- ✅ Assert production untouched
- **Trigger**: Main branch par merge ke baad

### 3. **Production Deployment** (Coming soon)
- Manual approval required
- Promote job with dry-run option
- Environment protection

## 🔧 Step-by-Step Setup

### **STEP 1: GitHub Secrets Configure Karo** ⚙️

1. GitHub repo mein jao: https://github.com/Entirework-blip/work
2. Settings → Secrets and variables → Actions
3. **New repository secret** par click karo
4. Do secrets add karo:

```
Name: DATABRICKS_HOST
Value: https://databricks.com

Name: DATABRICKS_TOKEN  
Value: <your-personal-access-token>
```

#### Token Kaise Generate Karein:
1. Databricks workspace mein login karo
2. Settings → User Settings → Access Tokens
3. **Generate New Token** click karo
4. Token name: `github-actions-ci`
5. Lifetime: **30 days** (security ke liye kam rakho)
6. Copy token aur GitHub secret mein paste karo

⚠️ **Security Warning**: Token kabhi file ya log mein mat likho!

---

### **STEP 2: Branch Protection Enable Karo** 🔒

1. GitHub Settings → Branches
2. **Add branch protection rule**
3. Branch name pattern: `main`
4. Enable yeh options:
   - ✅ **Require a pull request before merging**
   - ✅ **Require status checks to pass before merging**
     - Search aur select: `checks` (CI workflow)
   - ✅ **Require branches to be up to date before merging**
   - ✅ **Do not allow bypassing the above settings**
5. **Create** par click karo

---

### **STEP 3: First Commit & Push** 📤

```powershell
cd c:\Users\Zeenat\Downloads\files\mlops-sentiment-pipeline-main

# Git initialize (agar nahi hai)
git init

# Remote add
git remote add origin https://github.com/Entirework-blip/work.git

# Stage all files
git add .

# Commit
git commit -m "feat: Add CI/CD pipeline with prod isolation checks"

# Push to main
git push -u origin main
```

---

### **STEP 4: First Test - Create a PR** 🧪

```powershell
# New branch banao
git checkout -b test/ci-pipeline

# Koi chhota change karo (testing ke liye)
echo "# Testing CI" >> test.md

# Commit aur push
git add test.md
git commit -m "test: Verify CI pipeline"
git push -u origin test/ci-pipeline
```

GitHub pe jao aur **Pull Request** create karo:
- CI checks automatically run honge
- 3 checks pass hone chahiye:
  1. ✅ Lint
  2. ✅ Unit tests
  3. ✅ Bundle validate

---

## 📁 Project Structure

```
mlops-sentiment-pipeline-main/
├── .github/
│   └── workflows/
│       ├── ci.yml              # PR checks
│       └── deploy-test.yml     # Test deployment
├── config/                     # Configuration files
├── scripts/
│   └── assert_prod_untouched.py  # Prod isolation checker
├── src/                        # Source code
│   ├── 00_unit_tests.py
│   ├── 01_validate_data.py
│   ├── 02_train.py
│   ├── 03_gate.py
│   ├── 04_register.py
│   └── 05_promote.py
├── tests/                      # Test files
├── databricks.yml              # Bundle configuration
├── Makefile                    # Local commands
├── requirements-dev.txt        # Python dependencies
└── README.md
```

---

## 🛠️ Local Testing

### Install Dependencies
```powershell
pip install -r requirements-dev.txt
```

### Run All CI Checks Locally
```powershell
make ci
```

Yeh command run karega:
1. Ruff lint check
2. Unit tests
3. Bundle validation

### Test Full Deploy Pipeline Locally
```powershell
# Environment variables set karo
$env:DATABRICKS_HOST = "https://databricks.com"
$env:DATABRICKS_TOKEN = "your-token"

# Deploy test run karo
make deploy-test-local
```

---

## 🔍 Configuration Details

### Job Key
`INTEGRATION_JOB_KEY` in workflows: **`retrain_sentiment`**

Yeh tumhare `databricks.yml` se match karta hai:
```yaml
resources:
  jobs:
    retrain_sentiment:  # <-- Yeh job key
      name: retrain-sentiment-${bundle.target}
```

### Target
Pipeline **`integration_test`** target use karti hai:
```yaml
targets:
  integration_test:
    mode: development
    variables:
      model_name: project1.mlops_sentiment.sentiment_classifier_test
```

### Production Model
```python
PROD_MODEL = "project1.mlops_sentiment.sentiment_classifier"
```

---

## 🛡️ Security Features

| Feature | Implementation |
|---------|----------------|
| **Secrets Management** | GitHub Actions secrets (never in code) |
| **Token Rotation** | 30-day expiry recommended |
| **Minimal Permissions** | `contents: read` only |
| **Prod Isolation** | Automated before/after snapshots |
| **Branch Protection** | Direct push to main blocked |
| **Audit Trail** | Artifacts saved for every deployment |

---

## 📊 Workflow Status Badges

README mein badges add karne ke liye:

```markdown
![CI](https://github.com/Entirework-blip/work/actions/workflows/ci.yml/badge.svg)
![Deploy Test](https://github.com/Entirework-blip/work/actions/workflows/deploy-test.yml/badge.svg)
```

---

## 🐛 Troubleshooting

### Error: "Billing lock"
**Solution**: GitHub Settings → Billing → Public repo honi chahiye (free runners ke liye)

### Error: "DATABRICKS_TOKEN invalid"
**Solution**: 
1. Token regenerate karo (30-day expiry check karo)
2. GitHub Secrets update karo

### Error: "Bundle validate failed"
**Solution**:
```powershell
# Local test karo
databricks bundle validate -t integration_test
```

### Error: "pytest: command not found"
**Solution**:
```powershell
pip install -r requirements-dev.txt
```

### Error: "PYTHONPATH not set"
**Solution**: Already `ci.yml` mein set hai:
```yaml
env:
  PYTHONPATH: src
```

---

## ✅ Success Checklist

- [ ] GitHub secrets configured (`DATABRICKS_HOST`, `DATABRICKS_TOKEN`)
- [ ] Branch protection enabled for `main`
- [ ] First commit pushed to main
- [ ] Test PR created aur CI checks pass
- [ ] Deploy-test workflow ran successfully after merge
- [ ] Production snapshot verified (before == after)

---

## 🚀 Next Steps

1. **Immediate**:
   - [ ] Secrets configure karo
   - [ ] Branch protection enable karo
   - [ ] First test PR banao

2. **Soon**:
   - [ ] Production deployment workflow
   - [ ] Manual approval process
   - [ ] Slack/email notifications

3. **Future**:
   - [ ] Model performance monitoring
   - [ ] Automated rollback
   - [ ] Multi-environment strategy

---

## 📞 Support

Agar koi issue aaye ya help chahiye:
1. Workflow logs check karo: Actions tab → Failed workflow → Logs
2. Local testing karo: `make ci`
3. Error message share karo for debugging

---

**Built with ❤️ for Production-Ready MLOps**
