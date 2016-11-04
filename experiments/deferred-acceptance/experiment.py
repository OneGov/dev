import random
import transaction

from itertools import groupby, tee
from datetime import datetime, timedelta, date
from onegov.activity import Activity, ActivityCollection
from onegov.activity import Attendee, AttendeeCollection
from onegov.activity import Booking, BookingCollection
from onegov.activity import Occasion, OccasionCollection
from onegov.activity import PeriodCollection
from onegov.core.orm import Base
from onegov.core.orm.session_manager import SessionManager
from onegov.user import UserCollection
from sedate import overlaps
from boltons.setutils import IndexedSet
from statistics import mean, stdev
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from uuid import uuid4


def pairwise(iterable):
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


def yes_or_no(chance):
    return random.randint(0, 11) <= chance * 10


def weighted_random_choice(choices):
    limit = random.uniform(0, sum(w for c, w in choices))
    running_total = 0

    for choice, weight in choices:
        if running_total + weight >= limit:
            return choice
        running_total += weight


def random_spots():
    min_spots = random.randint(3, 6)
    max_spots = random.randint(min_spots, 10)

    return min_spots, max_spots


def drop_all_existing_experiments(dsn):
    mgr = SessionManager(dsn=dsn, base=Base)

    for schema in mgr.list_schemas(limit_to_namespace=Experiment.namespace):
        mgr.engine.execute('DROP SCHEMA "{}" CASCADE'.format(schema))

    transaction.commit()
    mgr.dispose()


class Experiment(object):

    namespace = 'da'

    def __init__(self, dsn, drop_others=True):
        self.mgr = SessionManager(dsn=dsn, base=Base, session_config={
            'expire_on_commit': False
        })

        # create a new one schema
        self.schema = '{}-{}'.format(self.namespace, uuid4().hex[:8])
        self.mgr.set_current_schema(self.schema)

    @property
    def session(self):
        return self.mgr.session()

    def query(self, *args, **kwargs):
        return self.session.query(*args, **kwargs)

    def drop_other_experiments(self):

        transaction.commit()

    def create_owner(self):
        return UserCollection(self.session).add(
            username=uuid4().hex,
            password=uuid4().hex,
            role='admin')

    def create_period(self):
        prebooking = [d.date() for d in (
            datetime.now() - timedelta(days=1),
            datetime.now() + timedelta(days=1)
        )]
        execution = [d.date() for d in (
            datetime.now() + timedelta(days=2),
            datetime.now() + timedelta(days=4)
        )]

        return PeriodCollection(self.session).add(
            title="Ferienpass 2016",
            prebooking=prebooking,
            execution=execution,
            active=True)

    def create_occasion(self, period, owner, overlap, previous):
        activities = ActivityCollection(self.session)

        activity = activities.add(
            title=uuid4().hex,
            username=owner.username
        )

        activity.propose().accept()

        if previous:
            if overlap:
                start = previous.end - timedelta(seconds=1)
            else:
                start = previous.end + timedelta(seconds=1)
        else:
            start = datetime.now()

        end = start + timedelta(seconds=60)

        return OccasionCollection(self.session).add(
            activity, period, start, end, 'Europe/Zurich',
            spots=random_spots()
        )

    def create_attendee(self, owner, name, birth_date):
        return AttendeeCollection(self.session).add(
            owner, name, birth_date)

    def create_booking(self, owner, attendee, occasion, priority):
        return BookingCollection(self.session).add(
            owner, attendee, occasion, priority)

    def create_fixtures(self, choices, overlapping_chance, attendee_count,
                        distribution):

        period = self.create_period()
        owner = self.create_owner()

        def in_batches(count, factory):
            result = []

            for ix in range(count):
                result.append(factory(result))

                if ix % 10 == 0:
                    transaction.commit()

            return result

        # create the occasions
        occasions = in_batches(choices, lambda r: self.create_occasion(
            period,
            owner,
            yes_or_no(overlapping_chance),
            r and r[-1]
        ))

        # create the attendees
        attendees = in_batches(attendee_count, lambda r: self.create_attendee(
            owner=owner,
            name=uuid4().hex,
            birth_date=date(2000, 1, 1)
        ))

        # create the bookings
        bookings = []

        for attendee in attendees:
            number_of_choices = weighted_random_choice(distribution)
            chosen = random.sample(occasions, number_of_choices)

            for ix, occasion in enumerate(chosen):
                bookings.append(
                    self.create_booking(
                        owner,
                        attendee,
                        occasion,
                        priority=ix < 3 and 1 or 0
                    )
                )

                if ix % 10 == 0:
                    transaction.commit()

        transaction.commit()

    @property
    def activity_count(self):
        return self.session.query(Activity).count()

    @property
    def occasion_count(self):
        return self.session.query(Occasion).count()

    @property
    def attendee_count(self):
        return self.session.query(Attendee).count()

    @property
    def booking_count(self):
        return self.session.query(Booking).count()

    @property
    def global_happiness_scores(self):
        return [score for score in (
            self.happiness(a)
            for a in self.session.query(Attendee).with_entities(Attendee.id)
        ) if score is not None]

    @property
    def global_happiness(self):
        return mean(self.global_happiness_scores)

    @property
    def global_happiness_stdev(self):
        return stdev(self.global_happiness_scores)

    def happiness(self, attendee):
        bookings = self.session.query(Booking)\
            .with_entities(Booking.state, Booking.priority)\
            .filter(Booking.attendee_id == attendee.id)

        bits = []

        for booking in bookings:
            bits.extend(
                booking.state == 'confirmed' and 1 or 0
                for _ in range(booking.priority + 1)
            )

        # attendees without a booking are neither happy nor unhappy
        if not bits:
            return None

        return sum(bits) / len(bits)

    @property
    def happiness_histogram(self):

        # necessary for this code to run directly in the buildout,
        # not just in the jupyter notebook alone
        import matplotlib.pyplot as plt
        from matplotlib.ticker import MaxNLocator

        figure = plt.figure("Happiness Histogram")
        subplot = figure.add_subplot(111)
        plt.ylabel('Number of Attendees')
        plt.xlabel('Happiness')

        plt.figtext(1.4, 0.875, "Global happiness: {:.2f}%".format(
            self.global_happiness * 100
        ), horizontalalignment='right')

        plt.figtext(1.4, 0.825, "Standard Deviation: {:.2f}%".format(
            self.global_happiness_stdev * 100
        ), horizontalalignment='right')

        plt.figtext(1.4, 0.775, "Operable courses: {:.2f}%".format(
            self.operable_courses * 100
        ), horizontalalignment='right')

        # force the yticks to be integers
        subplot.yaxis.set_major_locator(MaxNLocator(integer=True))

        scores = self.global_happiness_scores
        subplot.hist(scores, 10, color='#006fba', alpha=0.8)

        return plt.plot()

    @property
    def course_bookings_graph(self):

        # necessary for this code to run directly in the buildout,
        # not just in the jupyter notebook alone
        import matplotlib.pyplot as plt

        plt.ylabel('Number of Bookings')
        plt.xlabel('Course Index')

        scores = [
            len(o.bookings) for o in
            self.query(Occasion).options(joinedload(Occasion.bookings))
        ]

        plt.bar(list(range(len(scores))), sorted(scores))

        return plt.plot()

    @property
    def operable_courses(self):
        unconfirmed = self.session.query(Booking)\
            .with_entities(func.count(Booking.id).label('count'))\
            .filter(Booking.occasion_id == Occasion.id)\
            .filter(Booking.state == 'confirmed')\
            .subquery().lateral()

        o = self.session.query(Occasion, unconfirmed.c.count)

        bits = []

        for occasion, count in o:
            bits.append(count >= occasion.spots.lower and 1 or 0)

        if not bits:
            return 0

        return sum(bits) / len(bits)

    @property
    def overlapping_occasions(self):
        count = 0

        o = self.session.query(Occasion)
        o = o.order_by(Occasion.start, Occasion.end)

        for previous, current in pairwise(o):
            if current is None:
                continue

            if previous.end > current.start:
                count += 1

        return count / o.count()

    def reset_bookings(self):
        q = self.session.query(Booking)
        q = q.filter(Booking.state != 'unconfirmed')
        q.update({Booking.state: 'unconfirmed'}, 'fetch')

        transaction.commit()

    def pick_favorite(self, candidates, *args):
        """ Will simply pick the favorites first in the entered order. """
        return candidates.pop()

    def pick_random(self, candidates, *args):
        """ Will pick completely at random. """
        return candidates.pop(random.randint(0, len(candidates) - 1))

    def pick_random_but_favorites_first(self, candidates, *args):
        """ Picks at random, first only considering favorites, then considering
        everyone. """
        excited = [c for c in candidates if c.priority]

        if excited:
            pick = random.choice(excited)
        else:
            pick = random.choice([c for c in candidates if not c.priority])

        candidates.remove(pick)
        return pick

    def pick_least_impact_favorites_first(self, candidates, unconfirmed):
        """ Picks the favorite with the least impact amongst all unconfirmed
        bookings. That is the booking which will cause the least other
        bookings to be cancelled.

        """

        # yields the number of bookings affected by the given one
        def impact(candidate):
            impacted = 0

            for b in unconfirmed:
                if b.attendee_id == candidate.attendee_id:
                    is_impacted = overlaps(
                        b.occasion.start, b.occasion.end,
                        candidate.occasion.start, candidate.occasion.end
                    )
                    impacted += is_impacted and 1 or 0

            return impacted

        excited = [c for c in candidates if c.priority]

        if excited:
            pick = min(excited, key=impact)
        else:
            pick = min([c for c in candidates if not c.priority], key=impact)

        candidates.remove(pick)
        return pick

    def greedy_matching_until_operable(self, pick_function, safety_margin=0,
                                       matching_round=0):

        if matching_round == 0:
            self.reset_bookings()

        random.seed(matching_round)

        q = self.session.query(Booking)

        # higher priority bookings land at the end, since we treat the
        # candidates as a queue -> they end up at the front of the queue
        q = q.order_by(Booking.occasion_id, Booking.priority)
        q = q.options(joinedload(Booking.occasion))

        # read as list first, as the order matters for the grouping
        unconfirmed = list(q.filter(Booking.state == 'unconfirmed'))

        by_occasion = [
            (occasion, IndexedSet(candidates))
            for occasion, candidates
            in groupby(unconfirmed, key=lambda booking: booking.occasion)
        ]

        random.shuffle(by_occasion)

        # the order no longer matters
        unconfirmed = set(unconfirmed)
        confirmed = set(q.filter(Booking.state == 'confirmed'))
        cancelled = set(q.filter(Booking.state == 'cancelled'))

        for occasion, candidates in by_occasion:

            # remove the already cancelled or confirmed (this loop operates
            # on a separate copy of the data)
            candidates -= cancelled
            candidates -= confirmed

            # if there are not enough bookings for an occasion we must exit
            if len(candidates) < occasion.spots.lower:
                continue

            picks = set()
            collateral = set()

            required_picks = occasion.spots.lower + safety_margin

            while candidates and len(picks) < required_picks:

                # pick the next best spot
                pick = pick_function(candidates, unconfirmed)
                picks.add(pick)

                # keep track of all bookings that would be made impossible
                # if this occasion was able to fill its quota
                collateral |= set(
                    b for b in unconfirmed
                    if b.attendee_id == pick.attendee_id and
                    b not in picks and
                    overlaps(
                        b.occasion.start, b.occasion.end,
                        pick.occasion.start, pick.occasion.end
                    )
                )

                # remove affected bookings from possible candidates
                candidates -= collateral

            # if the quota has been filled, move the bookings around
            if len(picks) >= required_picks:

                # confirm picks
                confirmed |= picks
                unconfirmed -= picks

                # cancel affected bookings
                cancelled |= collateral
                unconfirmed -= collateral

        # write the changes to the database
        def update_states(bookings, state):
            ids = set(b.id for b in bookings)

            if not ids:
                return

            b = self.session.query(Booking)
            b = b.filter(Booking.id.in_(ids))
            b.update({Booking.state: state}, 'fetch')

        update_states(unconfirmed, 'unconfirmed')
        update_states(confirmed, 'confirmed')
        update_states(cancelled, 'cancelled')

        transaction.commit()

        self.assert_correctness()

    def assert_correctness(self):
        # make sure no confirmed bookings by attendee overlap
        q = self.query(Booking)
        q = q.filter(Booking.state == 'confirmed')
        q = q.options(joinedload(Booking.occasion))
        q = q.order_by(Booking.attendee_id)

        for attendee_id, bookings in groupby(q, key=lambda b: b.attendee_id):
            bookings = sorted(list(bookings), key=lambda b: b.occasion.start)

            for previous, current in pairwise(bookings):
                if previous and current:
                    assert not overlaps(
                        previous.occasion.start, previous.occasion.end,
                        current.occasion.start, current.occasion.end
                    )

        # make sure no course has bookings that amount to less than the
        # required amount
        q = self.query(Occasion)
        q = q.options(joinedload(Occasion.bookings))

        for occasion in q:
            if not occasion.bookings:
                continue

            # we don't want to confirm spots which do not lead to a filled
            # out occasion at this point - though we might have to revisit this
            confirmed = [
                b for b in occasion.bookings if b.state == 'confirmed']

            if confirmed:
                assert len(confirmed) >= occasion.spots.lower


if __name__ == '__main__':
    experiment = Experiment('postgresql://dev:dev@localhost:15432/onegov')
    experiment.create_fixtures(
        choices=10,
        overlapping_chance=0.1,
        attendee_count=1,
        distribution=[
            (1, 1.0),  # (number of choices, chance)
        ]
    )

    print("Happiness: {:.2f}%".format(experiment.global_happiness * 100))
    print("Courses: {:.2f}%".format(experiment.operable_courses * 100))
