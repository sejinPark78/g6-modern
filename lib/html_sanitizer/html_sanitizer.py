import abc
from copy import deepcopy
from typing import Dict, Set
import bleach

from core.exception import AlertException
from .allowed_dict import (
    common_allowed_tags_dict, common_allowed_attrs_dict,
    subject_private_allowed_tags_dict, subject_private_allowed_attrs_dict,
    content_private_allowed_tags_dict, content_private_allowed_attrs_dict
)


class BaseSanitizer(metaclass=abc.ABCMeta):
    def __init__(self, is_with_library_attrs: bool = False):
        self.base_allowed_tags_dict = deepcopy(common_allowed_tags_dict)
        self.base_allowed_attrs_dict = deepcopy(common_allowed_attrs_dict)

    def get_combined_filter_dict(
        self,
        base_allowed_dict: Dict[str, Set[str]],
        private_allowed_dict: Dict[str, Set[str]],
    ) -> Dict[str, Set[str]]:
        for key, tags in private_allowed_dict.items():
            base_allowed_dict[key] = base_allowed_dict.get(key, set()).union(tags)
        return base_allowed_dict

    @abc.abstractmethod
    def get_cleaned_data(self, html_content: str):
        pass


class SubjectSanitizer(BaseSanitizer):
    def __init__(self, is_with_library_attrs: bool = False):
        super().__init__(is_with_library_attrs)
        combined_tags = self.get_combined_filter_dict(self.base_allowed_tags_dict, subject_private_allowed_tags_dict)
        combined_attrs = self.get_combined_filter_dict(self.base_allowed_attrs_dict, subject_private_allowed_attrs_dict)

        self.allowed_tags = {tag for tags in combined_tags.values() for tag in tags if tag}
        self.allowed_attrs = {attr for attrs in combined_attrs.values() for attr in attrs if attr}

    def get_cleaned_data(self, html_content: str) -> str:
        cleaned_html = bleach.clean(
            html_content,
            tags=self.allowed_tags,
            attributes=self.allowed_attrs,
            strip=True
        )
        if not cleaned_html:
            raise AlertException("허용되지 않는 HTML 태그들을 변경후 제목을 다시 작성해주세요.", 400)
        return cleaned_html


class ContentSanitizer(BaseSanitizer):
    def __init__(self, is_with_library_attrs: bool = False):
        super().__init__(is_with_library_attrs)
        combined_tags = self.get_combined_filter_dict(self.base_allowed_tags_dict, content_private_allowed_tags_dict)
        combined_attrs = self.get_combined_filter_dict(self.base_allowed_attrs_dict, content_private_allowed_attrs_dict)

        self.allowed_tags = {tag for tags in combined_tags.values() for tag in tags if tag}

        attr_dict = {}
        for tag, attrs in combined_attrs.items():
            valid_attrs = [a for a in attrs if a]
            if tag == "common":
                attr_dict["*"] = valid_attrs
            else:
                attr_dict[tag] = valid_attrs

        self.allowed_attrs = attr_dict

    def get_cleaned_data(self, html_content: str) -> str:
        cleaned_html = bleach.clean(
            html_content,
            tags=self.allowed_tags,
            attributes=self.allowed_attrs,
            strip=True
        )
        return cleaned_html
