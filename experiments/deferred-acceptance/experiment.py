import random
import transaction

from itertools import groupby, tee
from datetime import datetime, timedelta, date
from onegov.activity import Activity, ActivityCollection
from onegov.activity import Attendee, AttendeeCollection
from onegov.activity import Booking, BookingCollection
from onegov.activity import Occasion, OccasionCollection
from onegov.activity import PeriodCollection
from onegov.activity.matching import match_bookings_with_occasions_from_db
from onegov.core.orm import Base
from onegov.core.orm.session_manager import SessionManager
from onegov.user import UserCollection
from sedate import overlaps
from boltons.setutils import IndexedSet
from statistics import mean, stdev
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from sortedcontainers import SortedSet
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
                booking.state == 'accepted' and 1 or 0
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
        accepted = self.session.query(Booking)\
            .with_entities(func.count(Booking.id).label('count'))\
            .filter(Booking.occasion_id == Occasion.id)\
            .filter(Booking.state == 'accepted')\
            .subquery().lateral()

        o = self.session.query(Occasion, accepted.c.count)

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
        q = q.filter(Booking.state != 'open')
        q.update({Booking.state: 'open'}, 'fetch')

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

    def pick_least_impact_favorites_first(self, candidates, open):
        """ Picks the favorite with the least impact amongst all open
        bookings. That is the booking which will cause the least other
        bookings to be blocked.

        """

        # yields the number of bookings affected by the given one
        def impact(candidate):
            impacted = 0

            for b in open:
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
        open = list(q.filter(Booking.state == 'open'))

        by_occasion = [
            (occasion, IndexedSet(candidates))
            for occasion, candidates
            in groupby(open, key=lambda booking: booking.occasion)
        ]

        random.shuffle(by_occasion)

        # the order no longer matters
        open = set(open)
        accepted = set(q.filter(Booking.state == 'accepted'))
        blocked = set(q.filter(Booking.state == 'blocked'))

        for occasion, candidates in by_occasion:

            # remove the already blocked or accepted (this loop operates
            # on a separate copy of the data)
            candidates -= blocked
            candidates -= accepted

            # if there are not enough bookings for an occasion we must exit
            if len(candidates) < occasion.spots.lower:
                continue

            picks = set()
            collateral = set()

            required_picks = occasion.spots.lower + safety_margin

            existing_picks = sum(
                1 for b in occasion.bookings if b.state == 'accepted')

            if existing_picks >= (occasion.spots.upper - 1):
                continue

            while candidates and len(picks) < required_picks:

                if len(picks) + existing_picks == occasion.spots.upper - 1:
                    break

                # pick the next best spot
                pick = pick_function(candidates, open)
                picks.add(pick)

                # keep track of all bookings that would be made impossible
                # if this occasion was able to fill its quota
                collateral |= set(
                    b for b in open
                    if b.attendee_id == pick.attendee_id and
                    b not in picks and
                    overlaps(
                        b.occasion.start, b.occasion.end,
                        pick.occasion.start, pick.occasion.end
                    )
                )

                # remove affected bookings from possible candidates
                candidates -= collateral

            # confirm picks
            accepted |= picks
            open -= picks

            # cancel affected bookings
            blocked |= collateral
            open -= collateral

        # write the changes to the database
        def update_states(bookings, state):
            ids = set(b.id for b in bookings)

            if not ids:
                return

            b = self.session.query(Booking)
            b = b.filter(Booking.id.in_(ids))
            b.update({Booking.state: state}, 'fetch')

        update_states(open, 'open')
        update_states(accepted, 'accepted')
        update_states(blocked, 'blocked')

        transaction.commit()

        self.assert_correctness()

    def builtin_deferred_acceptance(self):
        self.reset_bookings()
        match_bookings_with_occasions_from_db(
            self.session, PeriodCollection(self.session).query().first().id
        )
        transaction.commit()
        self.assert_correctness()

    def deferred_acceptance(self):
        self.reset_bookings()

        class AttendeePreferences(object):
            def __init__(self, attendee):
                self.attendee = attendee
                self.wishlist = SortedSet([
                    b for b in attendee.bookings
                    if b.state == 'open'
                ], key=lambda b: b.priority * -1)
                self.blocked = set()
                self.accepted = set()

            def __hash__(self):
                return hash(self.attendee)

            def __bool__(self):
                return len(self.wishlist) > 0

            def confirm(self, booking):
                self.blocked |= set(
                    b for b in self.wishlist
                    if hash(b) != hash(booking) and
                    overlaps(
                        booking.occasion.start, booking.occasion.end,
                        b.occasion.start, b.occasion.end
                    )
                )

                self.wishlist.remove(booking)
                self.accepted.add(booking)

            def unconfirm(self, booking):
                self.wishlist.add(booking)
                self.accepted.remove(booking)

                for x in self.blocked:
                    for y in self.blocked:
                        if hash(x) == hash(y):
                            break
                        if overlaps(x.occasion.start, x.occasion.end,
                                    y.occasion.start, y.occasion.end):
                            break
                    else:
                        self.wishlist.add(y)

                self.blocked -= self.wishlist

            def pop(self):
                return self.wishlist.pop(0)

        class OccasionPreferences(object):
            def __init__(self, occasion):
                self.occasion = occasion
                self.bookings = set(
                    b for b in occasion.bookings
                    if b.state == 'accepted'
                )
                self.attendees = {}

            def __hash__(self):
                return hash(self.occasion)

            @property
            def operable(self):
                return len(self.bookings) >= self.occasion.spots.lower

            @property
            def full(self):
                return len(self.bookings) == (self.occasion.spots.upper - 1)

            def score(self, booking):
                return booking.priority

            def match(self, attendee, booking):
                if not self.full:
                    self.attendees[booking] = attendee
                    self.bookings.add(booking)
                    attendee.confirm(booking)
                    return True

                for b in self.bookings:
                    if self.score(b) < self.score(booking):
                        attendee.confirm(booking)
                        self.attendees[b].unconfirm(b)
                        self.bookings.remove(b)
                        self.bookings.add(booking)
                        return True

                return False

        q = self.session.query(Attendee)
        q = q.options(joinedload(Attendee.bookings))
        unmatched = set(AttendeePreferences(a) for a in q)

        q = self.session.query(Booking)
        q = q.options(joinedload(Booking.occasion))

        all_bookings = q.all()

        preferences = {
            o: OccasionPreferences(o)
            for o in set(b.occasion for b in all_bookings)
        }
        occasions = {b: preferences[b.occasion] for b in all_bookings}

        while next((u for u in unmatched if u), None):

            if all(p.full for p in preferences.values()):
                break

            candidates = [u for u in unmatched if u]
            random.shuffle(candidates)

            matches = 0

            while candidates:
                candidate = candidates.pop()

                for booking in candidate.wishlist:
                    if occasions[booking].match(candidate, booking):
                        matches += 1
                        break

            if not matches:
                break

        # write the changes to the database
        def update_states(bookings, state):
            ids = set(b.id for b in bookings)

            if not ids:
                return

            b = self.session.query(Booking)
            b = b.filter(Booking.id.in_(ids))
            b.update({Booking.state: state}, 'fetch')

        open = set(b for a in unmatched for b in a.wishlist)
        accepted = set(b for a in unmatched for b in a.accepted)
        blocked = set(b for a in unmatched for b in a.blocked)

        update_states(open, 'open')
        update_states(accepted, 'accepted')
        update_states(blocked, 'blocked')

        transaction.commit()

        self.assert_correctness()

    def assert_correctness(self):
        # make sure no accepted bookings by attendee overlap
        q = self.query(Booking)
        q = q.filter(Booking.state == 'accepted')
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

        # make sure no course is overbooked
        q = self.query(Occasion)
        q = q.options(joinedload(Occasion.bookings))

        for occasion in q:
            if not occasion.bookings:
                continue

            # we don't want to confirm spots which do not lead to a filled
            # out occasion at this point - though we might have to revisit
            accepted = [
                b for b in occasion.bookings if b.state == 'accepted']

            if accepted:
                assert len(accepted) < occasion.spots.upper


if __name__ == '__main__':
    experiment = Experiment('postgresql://dev:dev@localhost:15432/onegov')
    experiment.create_fixtures(
        choices=5,
        overlapping_chance=0.5,
        attendee_count=100,
        distribution=[  # (number of choices, chance)
            (1, 1),
        ]
    )

    experiment.deferred_acceptance()

    print("Happiness: {:.2f}%".format(experiment.global_happiness * 100))
    print("Courses: {:.2f}%".format(experiment.operable_courses * 100))
