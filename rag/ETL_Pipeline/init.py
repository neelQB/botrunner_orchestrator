# from New_ETL_Pipeline.init import (
#     KnowledgeBase,
#     KBFiles,
#     KBText,
#     KBWebsite,
#     KBQuestions,
#     KBQuestionAnswer,
#     ETLStatus,
#     ETLTracker,
#     ETLRecordType
# )


class KnowledgeBase:
    pass


class KBFiles:
    pass


class KBText:
    pass


class KBWebsite:
    pass


class KBQuestions:
    pass


class KBQuestionAnswer:
    pass


class ETLStatus:
    PENDING = "PENDING", "Pending"
    IN_QUEUE = "IN_QUEUE", "In Queue"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"


class ETLRecordType:
    KNOWLEDGE_BASE = "KB", "Knowledge Base"
    KB_TEXT = "KB_TEXT", "KB Text"
    KB_FILE = "KB_FILE", "KB File"
    KB_WEBSITE = "KB_SITE", "KB Website"
    KB_QUESTION = "KB_QUEST", "KB Question"
    KB_QA = "KB_QA", "KB Question Answer"


model_choices_mapping = {
    KnowledgeBase: ETLRecordType.KNOWLEDGE_BASE,
    KBFiles: ETLRecordType.KB_FILE,
    KBText: ETLRecordType.KB_TEXT,
    KBWebsite: ETLRecordType.KB_WEBSITE,
    KBQuestions: ETLRecordType.KB_QUESTION,
    KBQuestionAnswer: ETLRecordType.KB_QA,
}


class ETLTracker:
    pass


model_choices_mapping = {
    KnowledgeBase: ETLRecordType.KNOWLEDGE_BASE,
    KBFiles: ETLRecordType.KB_FILE,
    KBText: ETLRecordType.KB_TEXT,
    KBWebsite: ETLRecordType.KB_WEBSITE,
    KBQuestions: ETLRecordType.KB_QUESTION,
    KBQuestionAnswer: ETLRecordType.KB_QA,
}

model_strings = [
    "KnowledgeBase",
    "KBFiles",
    "KBText",
    "KBWebsite",
    "KBQuestions",
    "KBQuestionAnswer",
]

string_model_mapping = {
    "KnowledgeBase": KnowledgeBase,
    "KBFiles": KBFiles,
    "KBText": KBText,
    "KBWebsite": KBWebsite,
    "KBQuestions": KBQuestions,
    "KBQuestionAnswer": KBQuestionAnswer,
}

from .extraction import Extractor
