# TX-Packages CI/CD Guide

## Overview

TX-Packages uses GitHub Actions for continuous integration and deployment. The pipeline automatically builds packages, generates the bootstrap image, and publishes releases.

## Workflows

### Main CI Pipeline (`.github/workflows/ci.yml`)

Triggered on:
- Push to `main` or `develop` branches
- Pull requests to `main`
- Version tags (`v*`)
- Manual workflow dispatch

### Pipeline Stages

```
Setup -> Validate -> Download -> Build -> Package -> Bootstrap -> Repository -> Test -> Publish
```

#### Stage 1: Setup

- Cache Android NDK installation
- Install Python and dependencies
- Configure environment variables

#### Stage 2: Validate

- Parse all recipe files
- Validate recipe format and content
- Run recipe parser tests

#### Stage 3: Resolve

- Build dependency graph
- Detect cycles
- Compute build order

#### Stage 4: Download

- Download upstream sources
- Verify SHA-256 checksums
- Cache downloads between builds

#### Stage 5: Build

- Build packages in parallel groups
- Matrix strategy by category
- Support incremental builds via cache

#### Stage 6: Package

- Generate `.txpkg` files
- Create package manifests

#### Stage 7: Bootstrap

- Install packages into empty prefix
- Generate default configuration
- Validate userspace
- Create `bootstrap.tar.zst`

#### Stage 8: Repository

- Generate `Packages` index
- Generate `Packages.json`
- Generate `SHA256SUMS`
- Generate `manifest.json`

#### Stage 9: Test

- Run full test suite
- Generate test report

#### Stage 10: Publish

- Create GitHub releases for tags
- Update nightly release for main branch

## Manual Dispatch

### Triggering Manually

1. Go to Actions tab in GitHub
2. Select "TX-Packages CI/CD"
3. Click "Run workflow"
4. Configure options:
   - **Target Android API**: Override default API level
   - **Packages**: Comma-separated list to build (empty = all)
   - **Skip Tests**: Skip test execution
   - **Debug Mode**: Enable verbose output

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `target_api` | Android API level | 29 |
| `packages` | Packages to build | All |
| `skip_tests` | Skip tests | false |
| `debug` | Debug mode | false |

## Caching Strategy

### NDK Cache

- Key: `tx-ndk-<api>-<recipe-hash>`
- Restores from previous NDK installations
- Saves ~500MB download on cache hit

### Download Cache

- Key: `tx-downloads-<recipe-hash>`
- Caches downloaded source tarballs
- Saves bandwidth and time for unchanged recipes

### Build Cache

- Content-addressable via recipe hash
- Skips unchanged packages
- Stored in `cache/` directory

## Artifacts

### Build Artifacts

| Artifact | Description | Retention |
|----------|-------------|-----------|
| `tx-downloads` | Downloaded sources | 7 days |
| `tx-build-*` | Build outputs by category | 7 days |
| `tx-packages` | Generated `.txpkg` files | 14 days |
| `tx-bootstrap` | Bootstrap image and manifest | 14 days |
| `tx-repository` | Repository metadata | 14 days |
| `tx-test-results` | Test results XML | 7 days |
| `tx-build-report` | Build summary report | 30 days |

### Artifact Usage

```bash
# Download artifacts via GitHub CLI
gh run download <run-id> --name tx-bootstrap

# Extract bootstrap
tar --zstd -xf bootstrap.tar.zst
```

## Releases

### Version Releases

Created automatically for tags matching `v*`:

```bash
# Create release tag
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

Release includes:
- Bootstrap image (`bootstrap.tar.zst`)
- SHA256SUMS
- Release notes with installation instructions

### Nightly Builds

Updated automatically on scheduled runs (if configured):

```yaml
on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM UTC daily
```

### Pre-releases

Tags containing `alpha`, `beta`, or `rc` are marked as pre-release:

```bash
git tag -a v1.1.0-beta.1 -m "Beta 1"
git push origin v1.1.0-beta.1
```

## Customization

### Adding Build Matrix Entries

Edit the build job matrix in `.github/workflows/ci.yml`:

```yaml
strategy:
  matrix:
    group: [core, shells, networking, compression, build-tools, languages, system, devel, doc, custom]
```

### Adding New Jobs

```yaml
  custom_job:
    name: Custom Step
    runs-on: ubuntu-latest
    needs: setup
    steps:
      - uses: actions/checkout@v4
      - name: Run custom step
        run: |
          # Your commands here
```

### Environment Variables

Set in workflow or repository settings:

```yaml
env:
  CUSTOM_VAR: value
```

Or via repository secrets for sensitive values.

## Troubleshooting

### Failed Builds

1. Check build logs in GitHub Actions
2. Download artifacts for failed jobs
3. Reproduce locally with same environment

### Cache Issues

```bash
# Clear caches via GitHub CLI
gh cache list
gh cache delete <key>
```

Or use the "Clear caches" button in Actions tab.

### Runner Issues

If runners fail:
1. Check runner disk space
2. Verify network access to upstream sources
3. Review NDK installation logs

## Security

### Secrets

Store sensitive values in GitHub Secrets:
- Signing keys (future)
- API tokens
- Credentials

### Permissions

Workflow uses minimal permissions:
```yaml
permissions:
  contents: write  # For releases
  actions: read
```

## Monitoring

### Build Notifications

Configure notifications for:
- Failed builds
- Completed releases
- Nightly build status

### Metrics

Track via GitHub API:
- Build duration
- Success rate
- Cache hit rate
