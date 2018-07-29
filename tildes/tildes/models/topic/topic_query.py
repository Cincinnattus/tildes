"""Contains the TopicQuery class."""

from typing import Any, Sequence

from pyramid.request import Request
from sqlalchemy.sql.expression import and_, null
from sqlalchemy_utils import Ltree

from tildes.enums import TopicSortOption
from tildes.lib.datetime import SimpleHoursPeriod, utc_now
from tildes.models.group import Group
from tildes.models.pagination import PaginatedQuery
from .topic import Topic
from .topic_visit import TopicVisit
from .topic_vote import TopicVote


class TopicQuery(PaginatedQuery):
    """Specialized query class for Topics."""

    def __init__(self, request: Request) -> None:
        """Initialize a TopicQuery for the request.

        If the user is logged in, additional user-specific data will be fetched
        along with the topics. For the moment, this is whether the user has
        voted on the topics, and data related to their last visit - what time
        they last visited, and how many new comments have been posted since.
        """
        super().__init__(Topic, request)

    def _attach_extra_data(self) -> 'TopicQuery':
        """Attach the extra user data to the query."""
        if not self.request.user:
            return self

        # pylint: disable=protected-access
        return self._attach_vote_data()._attach_visit_data()

    def _attach_vote_data(self) -> 'TopicQuery':
        """Add a subquery to include whether the user has voted."""
        vote_subquery = (
            self.request.query(TopicVote)
            .filter(
                TopicVote.topic_id == Topic.topic_id,
                TopicVote.user == self.request.user,
            )
            .exists()
            .label('user_voted')
        )
        return self.add_columns(vote_subquery)

    def _attach_visit_data(self) -> 'TopicQuery':
        """Join the data related to the user's last visit to the topic(s)."""
        if self.request.user.track_comment_visits:
            query = self.outerjoin(TopicVisit, and_(
                TopicVisit.topic_id == Topic.topic_id,
                TopicVisit.user == self.request.user,
            ))
            query = query.add_columns(
                TopicVisit.visit_time, TopicVisit.num_comments)
        else:
            # if the user has the feature disabled, just add literal NULLs
            query = self.add_columns(
                null().label('visit_time'),
                null().label('num_comments'),
            )

        return query

    @staticmethod
    def _process_result(result: Any) -> Topic:
        """Merge additional user-context data in result onto the topic."""
        if isinstance(result, Topic):
            # the result is already a Topic, no merging needed
            topic = result
            topic.user_voted = False
            topic.last_visit_time = None
            topic.comments_since_last_visit = None
        else:
            topic = result.Topic

            topic.user_voted = result.user_voted

            topic.last_visit_time = result.visit_time
            if result.num_comments is not None:
                new_comments = topic.num_comments - result.num_comments
                # prevent showing negative "new comments" due to deletions
                topic.comments_since_last_visit = max(new_comments, 0)

        return topic

    def apply_sort_option(
            self,
            sort: TopicSortOption,
            desc: bool = True,
    ) -> 'TopicQuery':
        """Apply a TopicSortOption sorting method (generative)."""
        if sort == TopicSortOption.VOTES:
            self._sort_column = Topic.num_votes
        elif sort == TopicSortOption.COMMENTS:
            self._sort_column = Topic.num_comments
        elif sort == TopicSortOption.NEW:
            self._sort_column = Topic.created_time
        elif sort == TopicSortOption.ACTIVITY:
            self._sort_column = Topic.last_activity_time

        self.sort_desc = desc

        return self

    def inside_groups(self, groups: Sequence[Group]) -> 'TopicQuery':
        """Restrict the topics to inside specific groups (generative)."""
        query_paths = [group.path for group in groups]
        subgroup_subquery = (
            self.request.db_session.query(Group.group_id)
            .filter(Group.path.descendant_of(query_paths))
        )

        return self.filter(
            Topic.group_id.in_(subgroup_subquery))  # type: ignore

    def inside_time_period(self, period: SimpleHoursPeriod) -> 'TopicQuery':
        """Restrict the topics to inside a time period (generative)."""
        return self.filter(Topic.created_time > utc_now() - period.timedelta)

    def has_tag(self, tag: Ltree) -> 'TopicQuery':
        """Restrict the topics to ones with a specific tag (generative)."""
        # casting tag to string really shouldn't be necessary, but some kind of
        # strange interaction seems to be happening with the ArrayOfLtree
        # class, this will need some investigation
        tag = str(tag)

        # pylint: disable=protected-access
        return self.filter(Topic._tags.descendant_of(tag))  # type: ignore

    def is_pinned(self, pinned: bool) -> 'TopicQuery':
        """Restrict the topics to be pinned or unpinned."""
        return self.filter(Topic.is_pinned == pinned)
