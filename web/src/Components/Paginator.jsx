import React from "react";

import Pagination from "react-bootstrap/Pagination";

const Paginator = ({ page, pages, pageSettings, fetchAlbums }) => {
  if (pages < 2) {
    return;
  } else if (pages < 8) {
    let items = [];
    for (let number = 1; number <= pages; number++) {
      items.push(
        <Pagination.Item
          key={number}
          active={number === page}
          onClick={() => fetchAlbums(number)}
        >
          {number}
        </Pagination.Item>
      );
    }

    return <Pagination>{items}</Pagination>;
  } else {
    let items = [];
    const offset = 3;
    const start = Math.max(page - offset, 1);
    const end = Math.min(page + offset, pages);

    for (let number = start; number <= end; number++) {
      items.push(
        <Pagination.Item
          key={number}
          active={number === page}
          onClick={() => fetchAlbums(number)}
        >
          {number}
        </Pagination.Item>
      );
    }

    return (
      <Pagination>
        <Pagination.First onClick={() => fetchAlbums(1)} />
        <Pagination.Prev onClick={() => fetchAlbums(page - 1)} />
        {start != 1 && <Pagination.Ellipsis disabled={true} />}

        {items}

        {end != pages && <Pagination.Ellipsis disabled={true} />}
        <Pagination.Next onClick={() => fetchAlbums(page + 1)} />
        <Pagination.Last onClick={() => fetchAlbums(pages)} />
      </Pagination>
    );
  }
};

export default Paginator;
