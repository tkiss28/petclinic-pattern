"""Offline manifest checks; requires Helm and PyYAML."""

import subprocess
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
IMAGE = "quay.io/example/petclinic@sha256:" + "a" * 64


class PetclinicChartTest(unittest.TestCase):
    def test_chart(self):
        for values in ([], ["-f", "values-global.yaml", "-f", "variants/prod/values-prod.yaml"]):
            with self.subTest(values=values):
                output = subprocess.check_output(
                    ["helm", "template", "petclinic", "charts/petclinic", *values,
                     "--set-string", f"petclinic.image={IMAGE}"],
                    cwd=ROOT, text=True,
                )
                resources = {doc["kind"]: doc for doc in yaml.safe_load_all(output)}
                self.assertEqual(set(resources), {"Deployment", "Service", "Route"})
                deployment = resources["Deployment"]["spec"]
                self.assertEqual(deployment["replicas"], 1)
                self.assertEqual(deployment["strategy"]["type"], "Recreate")
                pod = deployment["template"]
                self.assertEqual(resources["Service"]["spec"]["selector"], pod["metadata"]["labels"])
                self.assertFalse(pod["spec"]["automountServiceAccountToken"])
                self.assertTrue(pod["spec"]["securityContext"]["runAsNonRoot"])
                container = pod["spec"]["containers"][0]
                self.assertEqual(container["image"], IMAGE)
                env = {entry["name"]: entry["value"] for entry in container["env"]}
                self.assertEqual(env["DATABASE"], "h2")
                self.assertTrue(env["SPRING_DATASOURCE_URL"].startswith("jdbc:h2:mem:"))
                self.assertEqual(env["SPRING_H2_CONSOLE_ENABLED"], "false")
                self.assertEqual(env["MANAGEMENT_ENDPOINTS_WEB_EXPOSURE_INCLUDE"], "health")
                self.assertEqual(env["MANAGEMENT_ENDPOINT_HEALTH_PROBES_ENABLED"], "true")
                self.assertEqual(container["readinessProbe"]["httpGet"]["path"], "/actuator/health/readiness")
                route = resources["Route"]["spec"]
                self.assertEqual(route["to"]["name"], resources["Service"]["metadata"]["name"])
                self.assertEqual(route["tls"], {"termination": "edge", "insecureEdgeTerminationPolicy": "Redirect"})

    def test_image_is_required(self):
        result = subprocess.run(
            ["helm", "template", "petclinic", "charts/petclinic"],
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set petclinic.image", result.stderr)

    def test_pattern_wiring(self):
        values = yaml.safe_load((ROOT / "values-global.yaml").read_text())
        variant = values["main"]["variant"]
        group = yaml.safe_load((ROOT / f"variants/{variant}/values-{variant}.yaml").read_text())["clusterGroup"]
        app = group["applications"]["petclinic"]
        self.assertIsInstance(group["namespaces"], dict)
        self.assertIn(app["namespace"], group["namespaces"])
        self.assertEqual(app["path"], "charts/petclinic")
        self.assertTrue((ROOT / app["path"] / "Chart.yaml").is_file())
        self.assertTrue(values["global"]["singleArgoCD"])
        self.assertTrue(values["global"]["secretLoader"]["disabled"])
        self.assertTrue(values["main"]["multiSourceConfig"]["enabled"])
        self.assertEqual(group["subscriptions"], {})
        metadata = yaml.safe_load((ROOT / "pattern-metadata.yaml").read_text())
        self.assertEqual([item["name"] for item in metadata["variants"]], [variant])
        self.assertFalse(metadata["extra_features"]["spoke_support"])


if __name__ == "__main__":
    unittest.main()
