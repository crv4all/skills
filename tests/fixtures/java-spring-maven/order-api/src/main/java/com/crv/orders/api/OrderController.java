package com.crv.orders.api;

import com.crv.orders.domain.OrderService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class OrderController {
    private final OrderService service;

    public OrderController(OrderService service) {
        this.service = service;
    }

    @PostMapping("/api/orders")
    public ResponseEntity<String> create(@RequestBody String payload) {
        return ResponseEntity.ok(service.place(payload));
    }
}
