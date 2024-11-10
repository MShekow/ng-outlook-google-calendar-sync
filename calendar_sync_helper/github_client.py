import base64
import re
from datetime import datetime
from typing import Tuple, Optional

import github
from github.Repository import Repository

from calendar_sync_helper.constants import MAX_FILE_SIZE_LIMIT_BYTES


class GitHubClient:
    def __init__(self, url: str, personal_access_token: str):
        self._owner, self._repo, self._branch, self._path = self._extract_github_credentials(url)
        self._github_client = github.Github(auth=github.Auth.Token(personal_access_token))

    def check_data_and_pat_validity(self):
        # Make an actual request to verify that the PAT (and other data) is valid
        self._github_client.get_repo(f"{self._owner}/{self._repo}")

    def upload_file(self, content: bytes):
        repository = self._github_client.get_repo(f"{self._owner}/{self._repo}")

        commit_message = f"Upload calendar data: {datetime.now().isoformat()}"

        if file_sha_and_size := self._get_sha_and_size_of_file(repository):
            file_sha, _size = file_sha_and_size
            repository.update_file(self._path, commit_message, content, file_sha, branch=self._branch)
        else:
            repository.create_file(self._path, commit_message, content, branch=self._branch)

    def download_file(self) -> bytes:
        """
        Downloads the file, or returns an empty bytes object if the file cannot be found. Raises if something
        unexpected goes wrong, or if the file is too big.
        """
        repository = self._github_client.get_repo(f"{self._owner}/{self._repo}")
        # Note: normally, we should call contents = repository.get_contents(self._path, ref=self._branch)
        # and then return "contents.decoded_content". But that did not work in our experiments. For instance, for
        # a binary file with the following content:
        # b'\x1ba_\x127\x18$Of\xb9\xa0\x8f\x07[\xa9N\xcf\xa5\xa5}-\xf1{\x04\xac\x8c\x96\rv\x9b\x9ed\xf7y\xf2U\x0e\t\xe3\xe0\xdeo\xb4\x0e\x8b\x8f\x99T\xd3\xa1\xc2|\xea\x0f\xe4\xc26\xa2\x1a@'
        # (or, base64-encoded: 'G2FfEjcYJE9muaCPB1upTs+lpX0t8XsErIyWDXabnmT3efJVDgnj4N5vtA6Lj5lU06HCfOoP5MI2ohpA')
        # the value of contents.decoded_content would be wrong (too long). The contents b64-encoded data would also
        # be different:
        # 'G2FfEjcYJE9mwrnCoMKPB1vCqU7Dj8KlwqV9LcOxewTCrMWS4oCTDXbigLrF\nvmTDt3nDslUOCcOjw6DDnm/CtA7igLnCj+KEolTDk8Khw4J8w6oPw6TDgjbC\nohpA\n'
        # For that reason, we instead use the repository.get_git_blob() approach, which seems to work properly.
        file_sha_and_size = self._get_sha_and_size_of_file(repository)
        if not file_sha_and_size:
            return bytes()

        file_sha, file_size = file_sha_and_size
        if file_size > MAX_FILE_SIZE_LIMIT_BYTES:
            raise ValueError(f"Content is too large ({file_size} bytes)")

        blob = repository.get_git_blob(file_sha)
        return base64.b64decode(blob.raw_data["content"])

    def delete_file(self):
        # Only used by integration test code
        repository = self._github_client.get_repo(f"{self._owner}/{self._repo}")
        file_sha_and_size = self._get_sha_and_size_of_file(repository)

        if not file_sha_and_size:
            raise FileNotFoundError(f"File {self._path} not found in the repository.")

        file_sha, _ = file_sha_and_size
        commit_message = f"Delete calendar data: {datetime.now().isoformat()}"
        repository.delete_file(self._path, commit_message, file_sha, branch=self._branch)

    @staticmethod
    def _extract_github_credentials(url: str) -> Tuple[str, str, str, str]:
        pattern = r"https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/(?P<branch>[^/]+)/(?P<path>.+)"
        match = re.match(pattern, url)

        if match:
            owner = match.group("owner")
            repo = match.group("repo")
            branch = match.group("branch")
            path = match.group("path")
            return owner, repo, branch, path
        else:
            raise ValueError("URL does not match the expected pattern: "
                             "https://github.com/<owner>/<repo>/<branch>/<path>")

    def _get_sha_and_size_of_file(self, repository: Repository) -> Optional[Tuple[str, int]]:
        branch_ref = repository.get_git_ref(f"heads/{self._branch}")
        base_tree = repository.get_git_tree(branch_ref.object.sha, recursive=True)

        for elem in base_tree.tree:
            if elem.path == self._path:
                return elem.sha, elem.size
