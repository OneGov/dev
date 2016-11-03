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
            chosen = random.sample(
                occasions, weighted_random_choice(distribution))

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
        q.update({Booking.state: 'unconfirmed'}, 'fetch')

        transaction.commit()

    def greedy_matching_until_operable(self):
        self.reset_bookings()

        q = self.session.query(Booking)
        q = q.order_by(Booking.occasion_id, Booking.priority)
        q = q.options(joinedload(Booking.occasion))

        def grouped_by_state(state):
            return {
                occasion: set(bookings)
                for occasion, bookings in groupby(
                    q.filter(Booking.state == state),
                    key=lambda booking: booking.occasion
                )
            }

        unconfirmed = grouped_by_state('unconfirmed')
        confirmed = grouped_by_state('confirmed')
        cancelled = grouped_by_state('cancelled')

        occasions = self.session.query(Occasion).all()

        for occasion in occasions:
            for group in (unconfirmed, confirmed, cancelled):
                if occasion not in group:
                    group[occasion] = set()

        for occasion in occasions:
            candidates = set(unconfirmed.get(occasion) or tuple())

            picks = set()
            collateral = set()

            # if there are not enough bookings for an occasion we must exit
            if len(candidates) < occasion.spots.lower:
                continue

            while candidates and len(picks) < occasion.spots.lower:
                # pick the next best spot
                pick = candidates.pop()
                picks.add(pick)

                # find the bookings made impossible by this pick
                for o in unconfirmed:
                    collateral = collateral | set(
                        b for b in unconfirmed[o]
                        if b.attendee_id == pick.attendee_id and
                        b not in picks and
                        overlaps(
                            b.occasion.start, b.occasion.end,
                            pick.occasion.start, pick.occasion.end
                        )
                    )

                candidates = candidates - collateral

            if len(picks) >= occasion.spots.lower:
                unconfirmed[occasion] -= picks
                confirmed[occasion] |= picks
                cancelled[occasion] |= collateral
                cancelled[occasion] -= confirmed[occasion]

        # write the changes to the database
        def update_states(group, state):
            ids = set(o.id for s in group.values() for o in s)

            if not ids:
                return

            b = self.session.query(Booking)
            b = b.filter(Booking.id.in_(ids))
            b.update({Booking.state: state}, 'fetch')

        update_states(unconfirmed, 'unconfirmed')
        update_states(confirmed, 'confirmed')
        update_states(cancelled, 'cancelled')

        transaction.commit()


if __name__ == '__main__':
    experiment = Experiment('postgresql://dev:dev@localhost:15432/onegov')
    experiment.create_fixtures(
        choices=10,
        overlapping_chance=0.1,
        attendee_count=10,
        distribution=[
            (0, 0.1),  # 10% have no choice
            (1, 0.1),  # 10% have a single choice
            (2, 0.1),  # 10% have two choices
            (3, 0.2),  # 20% have three choices
            (4, 0.2),  # 20% have four choices
            (5, 0.1),  # 10% have five choices
            (6, 0.1),  # 10% have six choices
            (7, 0.1),  # 10% have seven choices
        ]
    )

    experiment.greedy_matching_until_operable()
    print("Global happiness: {:.2f}%".format(
        experiment.global_happiness * 100))
    print("Operable courses: {:.2f}%".format(
        experiment.operable_courses * 100))
