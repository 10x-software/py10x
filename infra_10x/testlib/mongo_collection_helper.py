from core_10x.nucleus import Nucleus

class MongoCollectionHelperStub:
    @classmethod
    def prepare_filter_and_pipeline(cls, serialized_traitable, filter, pipeline):
        rev_tag = Nucleus.REVISION_TAG()
        id_tag = '_id'
        for key in (rev_tag, id_tag):
            filter[key] = serialized_traitable.pop(key)

        rev_condition = {'$and': [{'$eq': ['$' + name, {'$literal': value}]} for name, value in serialized_traitable.items()]}

        # fmt: off
        update_revision = {
            '$cond': [
                rev_condition,         #-- if each field is equal to its prev value
                filter[rev_tag],       #       then, keep the revision as is
                filter[rev_tag] + 1    #       else, increment it
            ]
        }

        pipeline.append(
            {
                '$replaceRoot': {
                    'newRoot': {
                        id_tag:     filter[id_tag],
                        rev_tag:    update_revision,
                    }
                }
            }
        )
        # fmt: on

        pipeline.extend(
            {'$replaceWith': {'$setField': dict(field=field, input='$$ROOT', value={'$literal': value})}}
            for field, value in serialized_traitable.items()
        )
