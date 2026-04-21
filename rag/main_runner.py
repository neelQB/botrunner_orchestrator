import uuid


from emailbot.config.settings import logger
from rag.ETL_Pipeline.process_json import ETLPipeLine

if __name__ == "__main__":
    sample_json = {
        "id": f"{uuid.uuid4().hex}",
        "name": "KB CRM test11",
        "files": [
            {
                "id": f"{uuid.uuid4().hex}",
                "file": "https://prodapi.salesbot.cloud/media/2a6be9ab-a7b7-45ce-9432-2c4f9bb4accf/kb_files/Free_Test_Data_6MB_PDF_1.pdf",
                "status": {"value": "active", "label": "Active"},
            },
            #     {
            #         "id": f"{uuid.uuid4().hex}",
            #         "file": "http://localhost:7800/avadh_chat.md",
            #         "status": {
            #             "value": "active",
            #             "label": "Active"
            #         }
            #     },
            #     {
            #         "id": f"{uuid.uuid4().hex}",
            #         "file": "http://localhost:7800/priority%201.md",
            #         "status": {
            #             "value": "active",
            #             "label": "Active"
            #         }
            #     },
            #     {
            #         "id": f"{uuid.uuid4().hex}",
            #         "file": "http://localhost:7800/sales_finetune.md",
            #         "status": {
            #             "value": "active",
            #             "label": "Active"
            #         }
            #     },
            #     {
            #         "id": f"{uuid.uuid4().hex}",
            #         "file": "http://localhost:7800/sanjay_chat.md",
            #         "status": {
            #             "value": "active",
            #             "label": "Active"
            #         }
            #     },
            #     {
            #         "id": f"{uuid.uuid4().hex}",
            #         "file": "http://localhost:7800/vidisha.md",
            #         "status": {
            #             "value": "active",
            #             "label": "Active"
            #         }
            #     },
            #     {
            #         "id": f"{uuid.uuid4().hex}",
            #         "file": "http://localhost:7800/hard_objection_answers1.md",
            #         "status": {
            #             "value": "active",
            #             "label": "Active"
            #         }
            #     },
            #     {
            #         "id": f"{uuid.uuid4().hex}",
            #         "file": "http://localhost:7800/hard_objection_answers2.md",
            #         "status": {
            #             "value": "active",
            #             "label": "Active"
            #         }
            #     },
            # {
            #     "id": f"{uuid.uuid4().hex}",
            #     # "file": "https://mpbou.edu.in/uploads/files/HISTORY_OF_INDIA_FROM_THE_EARLIEST_TIME_122_AD.pdf",
            #     "file" : "https://api.salesbot.cloud/media/d802d43b-af6e-44fc-a647-368ee467e949/kb_files/ChemistBot_v003_1.pdf",
            #     "status": {
            #         "value": "active",
            #         "label": "Active"
            #     }
            # },
            # {
            #     "id": f"{uuid.uuid4().hex}",
            #     "file": "http://localhost:7800/DCR.pdf",
            #     "status": {
            #         "value": "active",
            #         "label": "Active"
            #     }
            # },
            # {
            #     "id": f"{uuid.uuid4().hex}",
            #     # "file": "http://localhost:7800/BIOS%201.pdf",
            #     "file": "http://localhost:7800/Chemist%20Bot.pdf",
            #     "status": {
            #         "value": "active",
            #         "label": "Active"
            #     }
            # },
        ],
        "websites": [
            {
                "id": f"{uuid.uuid4().hex}",
                "url": "https://quantumbot.ai/",
                "content": None,
            }
        ],
        # "question_answers": [
        #     {
        #         "id": "4c3e7219-3ecc-4484-8e88-65a5163f42a8",
        #         "title": "QT1",
        #         "questions": [
        #             {
        #                 "id": "d7be8482-77d4-421d-8a3d-f35e1f51e836",
        #                 "question": "test quest 1"
        #             },
        #             {
        #                 "id": "464b8c63-23a4-48b3-b9c5-cc5b2808f2a4",
        #                 "question": "test q2"
        #             }
        #         ],
        #         "answer": "ans1"
        #     },
        #     {
        #         "id": "5611a20f-5b29-473c-902f-211496e2b2bb",
        #         "title": "QT2",
        #         "questions": [
        #             {
        #                 "id": "37ed3a49-502d-474b-9874-d6b374fbd53e",
        #                 "question": "test 2 quest 1"
        #             },
        #             {
        #                 "id": "15b31b57-e923-4ab8-8636-ed5c5f35d87b",
        #                 "question": "test 2 q2"
        #             }
        #         ],
        #         "answer": "2ans1"
        #     },
        #     {
        #         "id": "5611a20f-5b29-473c-902f-211496e2b2bb",
        #         "title": "QT3",
        #         "questions": [
        #             {
        #                 "id": "37ed3a49-502d-474b-9874-d6b374fbd53e",
        #                 "question": "test 2 quest 1"
        #             },
        #             {
        #                 "id": "15b31b57-e923-4ab8-8636-ed5c5f35d87b",
        #                 "question": "test 2 q2"
        #             }
        #         ],
        #         "answer": "2ans1"
        #     },
        #     {
        #         "id": "5611a20f-5b29-473c-902f-211496e2b2bb",
        #         "title": "QT4",
        #         "questions": [
        #             {
        #                 "id": "37ed3a49-502d-474b-9874-d6b374fbd53e",
        #                 "question": "test 2 quest 1"
        #             },
        #             {
        #                 "id": "15b31b57-e923-4ab8-8636-ed5c5f35d87b",
        #                 "question": "test 2 q2"
        #             }
        #         ],
        #         "answer": "2ans1"
        #     },
        #     {
        #         "id": "5611a20f-5b29-473c-902f-211496e2b2bb",
        #         "title": "QT5",
        #         "questions": [
        #             {
        #                 "id": "37ed3a49-502d-474b-9874-d6b374fbd53e",
        #                 "question": "test 2 quest 1"
        #             },
        #             {
        #                 "id": "15b31b57-e923-4ab8-8636-ed5c5f35d87b",
        #                 "question": "test 2 q2"
        #             }
        #         ],
        #         "answer": "2ans1"
        #     },
        #     {
        #         "id": "5611a20f-5b29-473c-902f-211496e2b2bb",
        #         "title": "QT6",
        #         "questions": [
        #             {
        #                 "id": "37ed3a49-502d-474b-9874-d6b374fbd53e",
        #                 "question": "test 2 quest 1"
        #             },
        #             {
        #                 "id": "15b31b57-e923-4ab8-8636-ed5c5f35d87b",
        #                 "question": "test 2 q2"
        #             }
        #         ],
        #         "answer": "2ans1"
        #     },
        #     {
        #         "id": "5611a20f-5b29-473c-902f-211496e2b2bb",
        #         "title": "QT7",
        #         "questions": [
        #             {
        #                 "id": "37ed3a49-502d-474b-9874-d6b374fbd53e",
        #                 "question": "test 2 quest 1"
        #             },
        #             {
        #                 "id": "15b31b57-e923-4ab8-8636-ed5c5f35d87b",
        #                 "question": "test 2 q2"
        #             }
        #         ],
        #         "answer": "2ans1"
        #     }
        # ],
        "texts": [
            # {
            #     "id": f"{uuid.uuid4().hex}",
            #     "title": "QuantumBot company address",
            #     "description": "1101 to 1106 Sankalp Square 3B, Beside Bhavan Road, Beside Taj Shaking, Ahmedabad 380056, Gujarat, India"
            # },
            # {
            #     "id": f"{uuid.uuid4().hex}",
            #     "title": "What are your company working hours?",
            #     "description": "Our company operates from Monday to Friday, 10:00 AM to 7:00 PM (IST). For urgent support or critical issues, extended support can be arranged based on prior agreement."
            # },
            # {
            #     "id": f"{uuid.uuid4().hex}",
            #     "title": "Support Availability – 24/7 Support",
            #     "description": "Yes, 24/7 support is available for enterprise clients under a dedicated support or SLA plan."
            # },
            #     {
            #         "id": "text1234",
            #         "title": "Sample Text",
            #         "description": "This is a sample text description"
            #     },
            #     {
            #         "id": "text12345",
            #         "title": "Sample Text",
            #         "description": "This is a sample text description"
            #     }
        ],
        "created_at": "2025-10-01T11:37:02.606892Z",
        "status": {"value": "active", "label": "Active"},
        "is_deteled": False,
    }

    try:
        # run_pipeline_from_json(sample_json, tenant_id="production_v4")
        obj = ETLPipeLine(
            json_value=sample_json,
            etl_tracker_id=None,
            tenant_id=f"t_qaaaaaaaaaaaaaaaa_AISAaaa",
            kb_id="test-kb-id",
        )
        obj.run_pipeline_from_json()
        logger.info("Sample pipeline execution completed")
    except Exception as e:
        logger.error(f"Sample pipeline failed: {e}")
