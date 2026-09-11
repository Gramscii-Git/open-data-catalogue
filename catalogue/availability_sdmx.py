"""Reproject exact native SDMX graphs and observation bodies with the declared core."""

from dataclasses import asdict
from pathlib import Path

from .config import fields


def project(state, core_root):
    import sdg
    from lxml import etree
    from sdg.plugins.opendata.acquisition_contract import ReadReceipt
    from sdg.plugins.opendata.availability.build import combination
    from sdg.plugins.opendata.availability.capture import Capture
    from sdg.plugins.opendata.availability.records import Dataset
    from sdg.plugins.opendata.availability.selection import source_definition
    from sdg.plugins.opendata.availability.spec import BuildSpec
    from sdg.plugins.opendata.availability.writer import encoded
    from sdg.plugins.opendata.client import load_providers
    from sdg.plugins.opendata.drivers import CatalogRow, Structure
    from sdg.plugins.opendata.drivers.sdmx.catalog_sdmx import (
        _parse_dataflows,
        catalog_agency,
        required_language_text,
    )
    from sdg.plugins.opendata.drivers.sdmx.client_sdmx import (
        _parse_constraint_xml,
        _shape_csv,
    )
    from sdg.plugins.opendata.drivers.sdmx.index_sdmx import contract
    from sdg.plugins.opendata.drivers.sdmx.index_sdmx import project as observations
    from sdg.plugins.opendata.drivers.sdmx.structure_graph_sdmx import (
        structure_from_graph,
    )
    from sdg.plugins.opendata.drivers.sdmx.structures_sdmx import (
        require_available_codes,
    )

    if Path(sdg.__file__).resolve() != (core_root / "server/sdg/__init__.py").resolve():
        raise ValueError("offline projection imported a different core")
    inputs, manifest = state["inputs"], state["manifest"]
    configuration = manifest["configuration"]
    fields(configuration, {"providers.yaml", "sdmx-query.yaml", "levels.yaml"}, "offline SDMX configuration")
    config_paths = {}
    for name, asset in configuration.items():
        inputs.read(asset)
        path = inputs.path(asset["path"])
        if path.name != name:
            raise ValueError("offline configuration filename differs from its declared role")
        config_paths[name] = path
    if len({path.parent for path in config_paths.values()}) != 1:
        raise ValueError("offline SDMX configuration must share its declared directory")
    providers = load_providers(config_paths["providers.yaml"])
    BuildSpec.model_validate(state["specification"])
    fields(manifest["capture"], {"manifest", "responses"}, "offline original capture")
    capture_asset = manifest["capture"]["manifest"]
    inputs.read(capture_asset)
    responses = inputs.path(manifest["capture"]["responses"])
    capture = Capture(responses, inputs.path(capture_asset["path"]), capture_asset["sha256"])
    captured, by_request = {}, {}
    for key, entry in capture.manifest.responses.items():
        for suffix, sha in (("json", entry.metadata_sha256), ("body", entry.body_sha256)):
            path = responses / f"{key}.{suffix}"
            inputs.read({"path": str(path.relative_to(inputs.root)), "sha256": sha, "bytes": path.stat().st_size})
        metadata, body = capture.response(key, entry.bytes)
        receipt = ReadReceipt.model_validate(metadata["receipt"])
        if receipt.url in captured or receipt.request_sha256 in by_request:
            raise ValueError("offline capture repeats a native request identity")
        captured[receipt.url] = (receipt, body)
        by_request[receipt.request_sha256] = (receipt, body)
    for row in state["tables"]["partitions.jsonl"]:
        for value in row["receipts"]:
            receipt = ReadReceipt.model_validate(value)
            if receipt.request_sha256 not in by_request or by_request[receipt.request_sha256][0] != receipt:
                raise ValueError("indexed source receipt differs from the original sealed capture")
    contexts, definitions = {}, []
    for key, raw in state["datasets"].items():
        dataset = Dataset.model_validate_json(encoded(raw))
        scope = dataset.scope.request_grid
        contract(scope)
        provider = providers[dataset.provider]
        if provider.driver != "sdmx":
            raise ValueError("offline native graph projection requires an SDMX provider")
        catalogue_url = provider.extra["dataset_url_template"].format(dataset_id=dataset.dataset_id)
        catalogues = [value for url, value in captured.items() if url.split("?")[0] == catalogue_url]
        constraint_url = f"{provider.base_url.rstrip('/')}/{provider.extra['constraint_endpoint']}/{provider.extra['agency']}/{dataset.dataset_id}"
        if len(catalogues) != 1 or constraint_url not in captured:
            raise ValueError("offline graph projection lacks the exact original catalogue or Actual constraint")
        flows = _parse_dataflows(provider, catalogues[0][1])
        if len(flows) != 1 or flows[0]["df_id"] != dataset.dataset_id:
            raise ValueError("offline catalogue identifies a different native dataflow")
        flow = flows[0]
        language = provider.extra["catalog_language"]
        title = required_language_text(provider, flow["names"], language, dataset.dataset_id, "title")
        catalog = CatalogRow(provider.id, dataset.dataset_id, title, {**flow, "agency": catalog_agency(provider, flow, dataset.dataset_id)})
        native = state["graphs"][key]
        expected_url = f"{provider.base_url.rstrip('/')}/dataflow/{catalog.fields['agency']}/{dataset.dataset_id}/{catalog.fields['version']}?references=descendants"
        if native["receipt"]["url"] != expected_url:
            raise ValueError("offline native graph URL differs from the exact dataflow agency and version")
        parsed = _parse_constraint_xml(etree.fromstring(captured[constraint_url][1]))
        graph = structure_from_graph(native["body"], catalog, language, parsed["dims"], source_constraint=parsed["source_constraint"])
        require_available_codes(graph.dimensions)
        structure = Structure(graph.dimensions, parsed["time"], parsed["obs_count"], None, "dsd", graph.reference, graph.source_constraint)
        dimensions = {dimension["id"]: dimension for dimension in structure.dimensions}
        geography = {scope.geography.dimension} if scope.geography is not None else set()
        if set(scope.argument_axes) != dimensions.keys() or set(provider.extra["territory_dims"]) & dimensions.keys() != geography:
            raise ValueError("offline graph dimensions disagree with the exact declared projection")
        for request in scope.requests():
            for identity, dimension in dimensions.items():
                if str(request["arguments"][identity]) not in {value["code"] for value in dimension["values"]}:
                    raise ValueError("offline request is outside its exact native dimension domain")
        context = {"title": title, "axis_labels": {scope.argument_axes[identity]: dimension["name"] for identity, dimension in dimensions.items()},
                   "definition": {"catalogue": asdict(catalog), "structure": structure.definition()}}
        definition = source_definition(provider, context, scope)
        if definition != dataset.definition_sha256 or title != dataset.title:
            raise ValueError("offline native graph projection differs from the candidate definition")
        contexts[key] = (dataset, context)
        definitions.append({"provider": key[0], "dataset_id": key[1], "definition_sha256": definition, "source_reference": graph.reference})
    count = 0
    for partition in state["tables"]["partitions.jsonl"]:
        dataset, context = contexts[(partition["provider"], partition["dataset_id"])]
        scope, request = dataset.scope.request_grid, partition["request"]
        receipts = [ReadReceipt.model_validate(row) for row in partition["receipts"] if f"/data/{dataset.dataset_id}/" in row["url"]]
        if len(receipts) != 1:
            raise ValueError("offline partition requires one exact native observation response")
        receipt = receipts[0]
        body = by_request[receipt.request_sha256][1]
        selected = {dimension["id"]: str(request["arguments"][dimension["id"]]) for dimension in context["definition"]["structure"]["dimensions"]}
        geography = scope.geography.dimension if scope.geography is not None else None
        shaped = _shape_csv(body.decode("utf-8"), geography, expected_dimensions=selected)
        projected = [combination(scope, request, partition["id"], row) for row in observations(scope, request, context, shaped)]
        expected = [row for row in state["tables"]["combinations.jsonl"] if row["provider"] == partition["provider"] and row["dataset_id"] == dataset.dataset_id and row["partition"] == partition["id"]]
        if sorted(map(encoded, projected)) != sorted(map(encoded, expected)):
            raise ValueError("offline native observations differ from the exact candidate combinations")
        count += len(projected)
    if count != len(state["tables"]["combinations.jsonl"]):
        raise ValueError("offline observations do not cover the complete candidate")
    return {"definitions": definitions, "partitions": len(state["tables"]["partitions.jsonl"]), "combinations": count,
            "capture_responses": len(captured), "partitions_unchanged": True, "combinations_unchanged": True}
