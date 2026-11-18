# Petclinic Pattern

A single-cluster Validated Patterns learning lab: Spring Petclinic, one replica,
an in-memory H2 database, a ClusterIP Service, and an HTTPS OpenShift Route.
No database operator, persistent storage, Vault, or application-specific operators
are needed. The framework installs Validated Patterns and OpenShift GitOps operators.

## Where the content lives

- `values-global.yaml`: framework settings and the Petclinic container image.
- `variants/prod/values-prod.yaml`: namespace and local Helm application registration.
  `prod` is just the scaffold's variant name, not a production-readiness claim.
- `charts/petclinic/`: Deployment, Service, Route, and resource defaults.
- Application source remains in `../spring-petclinic/`, independently of this repo.
  The existing PostgreSQL manifests in its `k8s/` folder are deliberately not used.

## Supply your application image

Build the local source with its existing Maven wrapper and Containerfile. From
this repository, for example (replace `YOUR_ORG` with your own registry namespace):

```bash
cd ../spring-petclinic
./mvnw -DskipTests package
podman build -f Containerfile -t quay.io/YOUR_ORG/petclinic:lab-1 .
podman push quay.io/YOUR_ORG/petclinic:lab-1
```

Use your existing Maven settings if dependency resolution requires them. This
pattern does not copy credentials or change the application's build configuration.
Build for the cluster's CPU architecture. Use a public lab image, or configure
registry pull access separately for the pattern namespace; do not commit credentials.

Set `petclinic.image` in `values-global.yaml` to the published image reference.
Prefer the immutable digest returned by the push:

```yaml
petclinic:
  image: quay.io/YOUR_ORG/petclinic@sha256:YOUR_IMAGE_DIGEST
```

The empty image setting intentionally fails Helm rendering with an actionable error
until configured. No unrelated public Petclinic image is used as a fallback.

## Check locally

With Helm and Python/PyYAML installed, these checks need no cluster or real image:

```bash
helm lint charts/petclinic --set-string petclinic.image=example.com/petclinic:test
python3 -B -m unittest discover -s tests -v
```

After setting your real image, inspect what will be deployed:

```bash
helm template petclinic charts/petclinic -f values-global.yaml -f variants/prod/values-prod.yaml
```

## Deploy to your lab cluster

Use an OpenShift lab with cluster-admin installation permissions, sufficient
capacity for OpenShift GitOps plus the application, and Podman on your workstation.
Commit and push this pattern, including your image setting, to the branch tracked
by its upstream remote. Argo CD reads the remote repository, not your working copy.
The configured remote is SSH; the in-cluster GitOps service needs repository access
too. For a public repo, use an HTTPS origin; for a private repo, configure GitOps
repository credentials according to the Validated Patterns documentation.

After logging into the intended cluster with `oc`, install from this repository:

```bash
./pattern.sh make install
```

When Argo CD finishes syncing, inspect the application namespace and open the
HTTPS URL reported by the Route:

```bash
oc get applications.argoproj.io -A
oc get deployment,service,route -n petclinic-pattern
oc rollout status deployment/petclinic -n petclinic-pattern --timeout=5m
oc get route petclinic -n petclinic-pattern -o jsonpath='https://{.spec.host}{"\n"}'
```

## A small GitOps experiment

Add a `petclinic.resources.requests.cpu: 200m` override in `values-global.yaml`
(nested under the existing `petclinic` block), commit it, and push it. Watch the
Petclinic Argo CD application reconcile and roll out the changed Deployment. Then
change that managed CPU request in the OpenShift console: observe self-healing if
enabled, or sync the application explicitly to restore the Git version.

## Lab limitations

H2 data is lost whenever the pod restarts or rolls out. The single replica and
Recreate strategy avoid presenting multiple independent in-memory databases.
There is a brief outage on every rollout. Add a persistent external database
before scaling or keeping real data.

The Route uses edge TLS and redirects HTTP to HTTPS. Petclinic has no application
authentication: anyone who can reach the Route can use it. Use only dummy data
and a controlled lab. The deployment disables the H2 console and limits web
Actuator exposure to health, overriding the source's development defaults.
