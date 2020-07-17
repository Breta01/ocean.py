import logging

from ocean_utils.agreements.service_factory import ServiceDescriptor
from ocean_utils.agreements.service_types import ServiceTypes
from ocean_utils.agreements.service_agreement import ServiceAgreement

from ocean_lib.assets.asset_resolver import resolve_asset
from ocean_lib import ConfigProvider
from ocean_lib.web3_internal import Web3Helper

logger = logging.getLogger('ocean')


class OceanCompute:
    """Ocean assets class."""

    def __init__(self, ocean_auth, config, data_provider):
        self._auth = ocean_auth
        self._config = config
        self._data_provider = data_provider

    @staticmethod
    def build_cluster_attributes(cluster_type, url):
        """

        :param cluster_type:
        :param url:
        :return:
        """
        return {
            "type": cluster_type,
            "url": url
        }

    @staticmethod
    def build_container_attributes(image, tag, checksum):
        """

        :param image:
        :param tag:
        :param checksum:
        :return:
        """
        return {
            "image": image,
            "tag": tag,
            "checksum": checksum
        }

    @staticmethod
    def build_server_attributes(
            server_id, server_type, cpu, gpu, memory, disk, max_run_time
    ):
        """

        :param server_id:
        :param server_type:
        :param cpu:
        :param gpu:
        :param memory:
        :param disk:
        :param max_run_time:
        :return:
        """
        return {
            "serverId": server_id,
            "serverType": server_type,
            "cpu": cpu,
            "gpu": gpu,
            "memory": memory,
            "disk": disk,
            "maxExecutionTime": max_run_time
        }

    @staticmethod
    def build_service_provider_attributes(
            provider_type, description, cluster, containers, servers
    ):
        """

        :param provider_type:
        :param description:
        :param cluster:
        :param containers:
        :param servers:
        :return:
        """
        return {
            "type": provider_type,
            "description": description,
            "environment": {
                "cluster": cluster,
                "supportedContainers": containers,
                "supportedServers": servers
            }
        }

    @staticmethod
    def create_compute_service_attributes(
            price, timeout, creator, date_published, provider_attributes):
        """

        :param price:
        :param timeout:
        :param creator:
        :param date_published:
        :param provider_attributes:
        :return:
        """
        return {
            "main": {
                "name": "dataAssetComputingServiceAgreement",
                "creator": creator,
                "datePublished": date_published,
                "cost": Web3Helper.to_wei(price),
                "timeout": timeout,
                "provider": provider_attributes
            }
        }

    @staticmethod
    def _status_from_job_info(job_info):
        return {
            'ok': job_info['status'] not in (31, 32),
            'status': job_info['status'],
            'statusText': job_info['statusText']
        }

    @staticmethod
    def check_output_dict(output_def, consumer_account, data_provider, config=None):
        if not config:
            config = ConfigProvider.get_config()

        default_output_def = {
            'nodeUri': config.network_url,
            'brizoUri': data_provider.get_url(config),
            'brizoAddress': config.provider_address,
            'metadata': dict(),
            'metadataUri': config.aquarius_url,
            'owner': consumer_account.address,
            'publishOutput': 0,
            'publishAlgorithmLog': 0,
            'whitelist': [],
        }

        output_def = output_def if isinstance(output_def, dict) else dict()
        default_output_def.update(output_def)
        return default_output_def

    def create_compute_service_descriptor(self, attributes):
        """

        :param attributes:
        """
        compute_endpoint = self._data_provider.get_compute_endpoint(self._config)
        return ServiceDescriptor.compute_service_descriptor(
            attributes=attributes,
            service_endpoint=compute_endpoint
        )

    def start(self, did, consumer_account, transfer_tx_id, algorithm_did=None,
              algorithm_meta=None, output=None, job_id=None):
        """Start a remote compute job on the asset files identified by `did` after
        verifying that the provider service is active and transferring the
        number of data-tokens required for using this compute service.

        :param did: str -- id of asset that has the compute service
        :param consumer_account: Account instance of the consumer ordering the service
        :param transfer_tx_id: hex str -- id of the datatokens transfer transaction
        :param algorithm_did: str -- the asset did (of `algorithm` type) which consist of `did:op:` and
            the assetId hex str (without `0x` prefix)
        :param algorithm_meta: `AlgorithmMetadata` instance -- metadata about the algorithm being run if
            `algorithm` is being used. This is ignored when `algorithm_did` is specified.
        :param output: dict object to be used in publishing mechanism, must define
        :param job_id: str identifier of a compute job that was previously started and
            stopped (if supported by the provider's  backend)
        :return: str -- id of compute job being executed
        """
        assert algorithm_did or algorithm_meta, 'either an algorithm did or an algorithm meta must be provided.'

        output = OceanCompute.check_output_dict(output, consumer_account, data_provider=self._data_provider)
        asset = resolve_asset(did, metadata_store_url=self._config.aquarius_url)
        service_endpoint = self._get_service_endpoint(did, asset)

        sa = ServiceAgreement.from_ddo(ServiceTypes.CLOUD_COMPUTE, asset)
        tx_id = transfer_tx_id

        job_info = self._data_provider.start_compute_job(
            did,
            service_endpoint,
            consumer_account.address,
            self._auth.get(consumer_account),
            sa.index,
            asset.data_token_address,
            tx_id,
            algorithm_did,
            algorithm_meta,
            output,
            job_id
        )
        return job_info['jobId']

    def status(self, did, job_id, account):
        return OceanCompute._status_from_job_info(
            self._data_provider.compute_job_status(
                did,
                job_id,
                self._get_service_endpoint(did),
                account.address,
                self._auth.get(account)
            )
        )

    def result(self, did, job_id, account):
        info_dict = self._data_provider.compute_job_result(
            did,
            job_id,
            self._get_service_endpoint(did),
            account.address,
            self._auth.get(account),
        )
        return {
            'did': info_dict.get('resultsDid', ''),
            'urls': info_dict.get('resultsUrls', []),
            'logs': info_dict.get('algorithmLogUrl', [])
        }

    def stop(self, did, job_id, account):
        return self._status_from_job_info(
            self._data_provider.stop_compute_job(
                did,
                job_id,
                self._get_service_endpoint(did),
                account.address,
                self._auth.get(account)
            )
        )

    def restart(self, did, job_id, account):
        return self._status_from_job_info(
            self._data_provider.restart_compute_job(
                did,
                job_id,
                self._get_service_endpoint(did),
                account.address,
                self._auth.get(account),
            )
        )

    def delete(self, did, job_id, account):
        return self._status_from_job_info(
            self._data_provider.delete_compute_job(
                did,
                job_id,
                self._get_service_endpoint(did),
                account.address,
                self._auth.get(account),
            )
        )

    def _get_service_endpoint(self, did, asset=None):
        if not asset:
            asset = resolve_asset(did, self._config.aquarius_url)

        return ServiceAgreement.from_ddo(ServiceTypes.CLOUD_COMPUTE, asset).service_endpoint