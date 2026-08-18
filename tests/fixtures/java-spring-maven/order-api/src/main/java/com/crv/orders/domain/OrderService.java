package com.crv.orders.domain;

import com.crv.orders.infra.KafkaPublisher;
import com.crv.orders.infra.OrderRepository;

public class OrderService {
    private final OrderRepository repository;
    private final KafkaPublisher publisher;

    public OrderService(OrderRepository repository, KafkaPublisher publisher) {
        this.repository = repository;
        this.publisher = publisher;
    }

    public String place(String payload) {
        String id = repository.save(payload);
        publisher.publish("orders.created", id);
        return id;
    }
}
